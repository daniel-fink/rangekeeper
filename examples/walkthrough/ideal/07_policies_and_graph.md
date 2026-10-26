# Lesson 07: Policies and the model graph (ideal cells)

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
floors. Each use has its own market index from lesson 04's optional section.

```python
# cell 1
from datetime import date

import rangekeeper as rk
import helpers
```

```python
# cell 2
residential = rk.io.load(helpers.data_path("07_property_plan.model.json"))
use_paths = rk.io.load(helpers.data_path("04_use_indices.paths.json"))
plan = helpers.load_base_plan()
residential.rollups()                  # key, value rolled up, relationship, root and contributors
```

```python
# cell 3
assumptions = {"discount_rate": "7 %/year", "opex_growth": "3.5 %/year",
               "exit_cap_rate": "5 %", "rent_growth": "0 %/year", "b_land_share": "40 %"}
debt = {"leverage": "65 %", "loan_rate": "6 %/year", "equity_rate": "12 %/year"}
assign = {"use_index": {"hotel": "hotel_index", "residential": "residential_index",
                        "retail": "retail_index"}}
fixed = residential.specify("Fixed design").fix(**plan.inputs, **plan.use_rates,
                                                **assumptions, **debt, provision="0 AUD")
```

## 2. A design alternative

Narrative: a paid provision lets Building B open as a hotel in place of residential.
It is not a new rent label. A hotel needs more cores and plant, so the alternative
changes the structure: the floors take the hotel use, and new cores and services
join Building B. Make it as a new revision of the same Model.

```python
# cell 4
e = residential.edit(name="Building B as hotel")
e.relabel(rk.model.Filter(classification="floor", within="building_b"), use="hotel")
e.include(helpers.load_fragment("building_b_hotel_services"))   # cores and plant, with costs
hotel = e.commit()
```

```python
# cell 5
rk.model.diff(residential, hotel)      # relabelled floors, added entities and relationships
```

Narrative. **Predict:** which of Building B's totals change? Roll up the same values
over both structures.

```python
# cell 6
for design in (residential, hotel):
    nla = design.rollup("nla", over="spatiallyContains", root="building_b",
                        contributors=rk.model.Filter(classification="floor"))
    cost = design.rollup("build_cost", over="spatiallyContains", root="building_b",
                         contributors=rk.model.Filter(has="build_cost"))
    print(design.name, nla.pivot(columns="use"), cost.value)
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
timing = rk.io.load(helpers.data_path("05_strategy.specification.json")).rules
timing                                 # lesson 05's three rules, as written there
switch = (fixed.alternatives(b_design={"residential": residential, "hotel": hotel})
          .fix(provision="2.5e6 AUD")
          .decide("b_design", when="hotel_index >= 1.10 * residential_index", review="year",
                  window=("shared_start + 1 year", "b_start"), otherwise="residential"))
```

```python
# cell 8
strategies = {
    "fixed": fixed,
    "timing": fixed.with_rules(timing),
    "switch": switch,
    "both": switch.with_rules(timing),
}
outcomes = {name: rk.execution.solve(spec.across(use_paths, assign=assign))
            for name, spec in strategies.items()}
```

## 4. Paired comparison of four strategies

Narrative: every strategy ran on the same paths. Compare each with the fixed
design, path by path. The provision is in every path of `switch` and `both`, also
where Building B stays residential.

```python
# cell 9
comparison = rk.execution.compare(outcomes, "equity_npv", "peak_shortfall", baseline="fixed")
comparison.summary()                   # mean difference, share better, 5 % quantile
```

```python
# cell 10
helpers.plot_target_curve(*(o.distribution("equity_npv") for o in outcomes.values()),
                          names=list(outcomes))
```

## 5. What gets built

Narrative: report the delivered projects as well as their value. How often does
Building B open as a hotel, and when? What is the use mix of the realised design?

```python
# cell 11
both = outcomes["both"]
both.table("b_design", "start_date", "b_open").group_by("b_design").len()
```

```python
# cell 12
both.rollup("nla", over="spatiallyContains", root="property",
            contributors=rk.model.Filter(classification="floor")).pivot(columns="use").describe()
```

## 6. The largest justified premium

Narrative: the provision is paid at the start, from equity. If the rules do not
depend on its cost, every dollar of provision lowers the equity NPV by its present
value on every path. Then the largest justified premium under the mean criterion is
the mean paired gain without the provision. **Check the "if" first**: run the
strategy at several provision costs and confirm that the decisions are the same.

```python
# cell 13
premiums = {p: {"provision": p} for p in ("0 AUD", "2.5e6 AUD", "5e6 AUD", "7.5e6 AUD")}
sweep = rk.execution.solve(strategies["both"].cases(premiums).across(use_paths, assign=assign))
sweep.decisions().same_across_cases()   # are the decisions the same at every premium?
```

```python
# cell 14
gain = sweep.compare(outcomes["timing"], "equity_npv").by_case()
gain.summary()
gain.breakeven("provision", criterion="mean")
```

> **Finance note.** The provision uses equity and funding headroom that Building B's
> rule needs. If the decisions change with the premium, read the largest justified
> premium from the sweep, not from one run. State the criterion: a mean criterion
> and a 5 % quantile criterion give different premiums.

## 7. Choose on one path set, test on another

Narrative: a threshold chosen on the same paths that test it looks better than it is.
Choose the switch threshold on lesson 04's paths, then test it on new paths from the
same generator with a new seed.

```python
# cell 15
thresholds = {t: {"switch_threshold": t} for t in (1.00, 1.05, 1.10, 1.20)}
tunable = (strategies["both"].parameters(switch_threshold=1.10)
           .decide("b_design", when="hotel_index >= switch_threshold * residential_index",
                   review="year", window=("shared_start + 1 year", "b_start"),
                   otherwise="residential").cases(thresholds))
train = rk.execution.solve(tunable.across(use_paths, assign=assign))
best = train.compare(outcomes["timing"], "equity_npv").by_case().best(criterion="mean")
```

```python
# cell 16
fresh = use_paths.generator.generate(periods=use_paths.periods, seed=2028, count=len(use_paths))
test = rk.execution.solve(tunable.cases({best: thresholds[best]}).across(fresh, assign=assign))
baseline = rk.execution.solve(strategies["timing"].across(fresh, assign=assign))
test.compare(baseline, "equity_npv").summary()   # usually less than on the training paths
```

## Optional: vertical expansion

Narrative: stronger structure in Building A, paid now, lets it add three floors
later. The expanded design adds the floors, labelled `phase="expansion"`. Building
A's own rollups count only `phase="base"` floors, so the new floors need their own
rollups and their own dates. The floor equations of lesson 06 apply to the new floors
too, because they match the same filter. A rule decides the expansion date.

```python
# cell 17
e = residential.edit(name="Building A expanded")
e.include(helpers.load_fragment("building_a_extra_floors"))
extra = rk.model.Filter(classification="floor", labels={"phase": "expansion"})
e.rollup("x_income", of="income", over="spatiallyContains", root="building_a", contributors=extra)
e.rollup("x_cost", of="build_cost", over="spatiallyContains", root="building_a", contributors=extra)
e.values(expansion_date="date")
e.extend("works", "- spread(x_cost, start=expansion_date, years=1)")
e.extend("income", "+ grow(x_income, rate=rent_growth, base=base_date, start=expansion_date + 1 year)")
expanded = e.commit()
```

```python
# cell 18
expand = (strategies["both"].alternatives(a_design={"base": residential, "expanded": expanded})
          .fix(a_provision="1.5e6 AUD")
          .decide("expansion_date", when="residential_index >= 1.25", review="year",
                  window=("a_open + 3 years", date(2035, 1, 1)), otherwise="never"))
rk.execution.solve(expand.across(use_paths, assign=assign)).compare(outcomes["both"], "equity_npv").summary()
```

## Exercises

**Try it 1: the cost of a provision never used.** On how many paths does Building B
stay residential? What does the switch strategy lose on those paths?

```python
# solution
switch_vs_fixed = outcomes["switch"].compare(outcomes["fixed"], "equity_npv")
switch_vs_fixed.where(b_design="residential").summary()
```

**Try it 2: a cautious criterion.** Find the largest justified premium under the 5 %
quantile criterion.

```python
# solution
gain.breakeven("provision", criterion=("quantile", 0.05))
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
assert len({o.run.market_paths for o in outcomes.values()}) == 1      # the same paths
provision_paid = both.table("provision_cost")["provision_cost"]
assert (provision_paid < 0).all()                                     # paid on every path
assert both.case(use_paths.keys[0]).model.id in {residential.id, hotel.id}
assert rk.model.diff(residential, hotel).added_entities              # a structural change
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

16 core code cells, 2 optional cells and 1 check cell (budget 20–25), 3 exercise
solutions. Cell 15 has 9 lines.

## Rule check

| Cell | Rules | Result |
| --- | --- | --- |
| 2 | 1, 10 | G26; G59: `Model.rollups()` table |
| 3 | 2, 4 | G43 (keyed values); G60: `assign` maps a keyed Flow value to several path names |
| 4 | 2, 7 | G61: `edit(name=)`, `relabel(filter, **labels)`, `include(fragment)`; `Filter(within=)` ([#121](https://github.com/daniel-fink/rangekeeper/issues/121)) |
| 5 | 7 | G62: `rk.model.diff(a, b)` with typed parts |
| 6 | 7, 11 | G39; display in plain Python |
| 7 | 2, 6 | G63: `Specification.alternatives(key={name: Model})` and a decided Model choice; G49, G55 |
| 7 | 1, 10 | G64: `Specification.rules` reads the rules of a saved Specification, so lesson 05's rules are loaded as a document, not from a helper |
| 8 | 2 | G65: `Specification.with_rules(rules)` |
| 9–10 | 8 | G66: `rk.execution.compare(mapping, *keys, baseline=)` for several strategies |
| 11 | 8 | G20, G51 (decided values in tables) |
| 12 | 7, 8 | G46 for batches: `Outcome.rollup(...)` over each case's realised Model |
| 13 | 8 | G67: `decisions().same_across_cases()` |
| 14 | 8 | G68: `by_case().breakeven(key, criterion=)` and `best(criterion=)` |
| 15 | 2 | G57 |
| 16 | 4, 6 | G69: `MarketPaths.generator` rebuilds the generator from the capture record |
| 17 | 2, 3 | G61, G17; G27 (`extend` adds terms to one side of an equation) |
| 18 | 6 | G63 with two alternative keys at once |
| 19 | 8 | G62, G33 |

## Cells for #214

The design for structural variants must support:

- **Alternatives as Model revisions.** `edit()`, `relabel`, `include` and `commit`
  make each option (cell 4). The options share the subject and the relations; they
  differ in structure.
- **A bounded choice in the Specification.** `alternatives(key={name: Model})` pins
  each option's revision. The choice is a decided value with a window and a default
  (cell 7). Several choices can be open at once (cell 18).
- **Realised structure per path.** Each case's Outcome carries the realised Model, so
  rollups and pivots work per path and across the batch (cells 11–12).
- **Provision on every path.** The provision is an ordinary fixed value in the
  Specification, and its cash flow is in every option's relations (cells 7, 13, 19).
- **Paired evaluation.** All strategies on one pinned `MarketPaths`, compared by path
  against a named baseline (cells 9, 14, 16).
- **Kept apart from optimisation.** Threshold and premium sweeps are cases. Nothing
  searches the rule space (cells 13, 15).
