# ADR-022: Choose between design alternatives with rules

Status: proposed. Recorded: 2026-10-27.

## Problem

Walkthrough lesson 07 asks which design provisions are worth paying for now
([ADR-020](020-walkthrough-plan-v2.md#07-policies-and-the-model-graph)). Its
proposed cells (#201) use two provisions:

- **Building B use switch:** a paid provision lets B open as a hotel in place of
  residential. The hotel changes the floors' use, and it adds cores, plant and
  their costs. This is a change to the structure, not a new rent label.
- **Vertical expansion:** stronger structure in Building A, paid now, lets A add
  floors later.

Decision D10 of #201 sets the shape: each design option is its own Model
revision. The Specification lists the options, and the choice is a decided value
([ADR-021](021-sequential-decisions.md)). A provision cost is a fixed value.

The library has no way to do this:

- A Specification pins exactly one Model revision
  ([ADR-001](001-document-roots.md)).
- Nothing records which design each path built.
- There is no comparison of several strategies on the same paths.
- There is no method to find the largest premium that a provision justifies.

The design must stay apart from optimisation. The best strategy tested is not a
global optimum.

## Choice

### Terms

| Term | Meaning | Name |
| --- | --- | --- |
| Alternative | One design option: a Model revision that a Specification names | — |
| Choice key | A Specification value whose options are alternatives. It is fixed or decided | `alternatives(...)` |
| Realised Model | The alternative that one case used | `case.model` |
| Provision | The cost of keeping an option open. It is an ordinary fixed value | — |
| Strategy | One Specification in a comparison | — |

### Declare alternatives

`Specification.alternatives(...)` returns a new Specification. It has two forms:

```python
# one choice key
spec.alternatives(b_design={"residential": residential, "hotel": hotel})

# several choice keys: the author supplies each combination
spec.alternatives(keys=("b_design", "a_design"), models={
    ("residential", "base"): residential,
    ("hotel", "base"): hotel,
    ("residential", "expanded"): residential_expanded,
    ("hotel", "expanded"): hotel_expanded,
})
```

These rules apply:

- **A choice key is a Specification value,** not a Model value. Its role is fixed
  (`fix(b_design="hotel")`) or decided (`decide(key="b_design", ...)`). A free
  choice key is rejected, because that would be optimisation.
- **A rule for a choice key must give `then=`**, for example
  `then="hotel", otherwise="residential"` (ADR-021).
- **Each reachable combination must have a Model.** A fixed key reaches one option.
  A decided key reaches its `then` and `otherwise` options. A missing combination
  gives `ValidationError` with the code `missing_alternative`, which names it.
- **The alternatives must agree.** Each reference that the Specification fixes,
  decides, observes or assigns from a path must resolve in every reachable
  alternative, with the same units. Alternatives made by `edit()` from one Model
  keep the identities of their shared declarations
  ([ADR-015](015-authoring.md)). A reference that does not resolve gives the code
  `alternative_mismatch`.
- **The Specification pins every alternative** by revision UUID. This amends
  ADR-001: a Specification can pin more than one Model revision. `on(model=)` is
  rejected on a Specification with alternatives; call `alternatives` again.

### How a rule chooses a design

A rule decides a choice key in the same way that it decides a date (ADR-021):

- **Before the decision,** the provisional solve uses the combination of the
  current provisional values. For a decided key, this is its `otherwise` option.
- **After the decision,** the evaluation uses the chosen alternative for the rest
  of the path.
- **The past does not change.** The chosen alternative must give the same
  Movements as the provisional one before the decision date. If not, the case fails
  with `decision_changes_past`. In lesson 07, both alternatives pay the provision
  at the site purchase, and B's works start after the choice.
- **The written order matters.** Choose the design before the rule that reads its
  cost. If a rule reads a solved value that a later rule's choice can change,
  `decide` rejects it with `rule_order`.

### Realised structure for each path

- **Each case records its realised Model** in the Run: the option names and the
  revision UUID. `outcome.case(key=...).model` returns that revision.
- **`outcome.rollup(of=, over=, root=, contributors=)`** runs the rollup on each
  case's realised Model with that case's solved values. The batch result has
  `pivot(...)` and `describe()`.
- **`outcome.table("b_design", ...)`** shows the chosen option name for each case.
- **Limit.** An entity whose delivery depends on a decided date, such as an
  expansion floor when `expansion_date` is `never`, is still in the realised
  Model. Report its delivery through its dated Flows and the decided date. A
  rollup that knows about delivery dates is not in 1.0.

### Paired comparison of strategies

`rk.execution.compare(outcomes={name: outcome, ...}, keys=, baseline=)` returns a
`StrategyComparison`:

- All Outcomes must pin the same `MarketPaths`. If not, it raises
  `different_market_paths`.
- It pairs each strategy with the baseline by path member key, as
  `Outcome.compare` does (ADR-021). Strategies can use different alternatives.
- It has `summary()` and `select(*names)`.
- A provision is a fixed value in every alternative of a strategy. Its cost is in
  every path, also where the option is never used. The comparison needs no special
  rule for it.

### The premium question

The provision is paid from equity, so it reduces the funding headroom. A rule
such as `funding.headroom >= b_cost` can then decide differently as the premium
rises. The library makes this visible and does not hide it:

- **Sweep the premium as cases:** `cases(cases={p: {"provision": p} for p in ...})`
  across the paths.
- **`outcome.decisions().same_across_cases()`** shows, for each path, if any decided
  value changes between the cases. It lists the paths and keys that change.
- **`comparison.by_case().breakeven(key="provision", criterion=...)`** gives the
  largest premium at which the criterion of the paired gains is zero or more.
  `criterion` is `"mean"` or `("quantile", q)`.
  - It needs at least two cases that differ only in `key`.
  - If a decided value changes on any path between the cases, it raises
    `DecisionsChangedError` with the code `decisions_changed`. The error lists the
    paths and keys. The reader then reads `by_case().summary()`.
  - If no decided value changes, each path's gain is affine in the premium,
    because the solve is affine and the decisions are fixed. `breakeven` fits a
    line for each path from the cases and solves the criterion exactly. It runs
    no new solve.
  - A third case checks the lines. If a case is not on its line within tolerance,
    `breakeven` raises `ValidationError` with the code `sweep_not_affine`. This
    happens when the compared key is not affine in the premium, for example a key
    that uses `max`.

### Kept apart from optimisation

- A choice key cannot be free. The library has no objective over alternatives.
- `by_case().best(criterion=)` returns the best tested case. The result says
  "best tested".
- To test thresholds on new paths, `MarketPaths.generator` rebuilds the generator
  from the capture record (#201 gap G69). A new seed gives a test set. Nothing in
  the library tunes a threshold.

## Worked examples

These come from the proposed cells of lesson 07 (#201). Amounts are illustrative.

**A rule chooses the design (cell 7, with `then`).**

```python
switch = (fixed.alternatives(b_design={"residential": residential, "hotel": hotel})
          .fix(provision="2.5e6 AUD")
          .decide(key="b_design", when="hotel_index >= 1.10 * residential_index",
                  review=yearly, window=("shared_start + 1 year", "b_start"),
                  then="hotel", otherwise="residential"))
both = switch.with_rules(rules=timing)    # start_date, b_start, b_sale_date follow
```

**The design before the start, on one date.** In `both`, the design rule is
written first. In January 2030 on one path:

| Observed | Value |
| --- | --- |
| `hotel_index >= 1.10 * residential_index` | true |
| `rent_index >= 1.10` | true |
| `funding.headroom` | 40 M AUD |
| `b_cost` as residential, as hotel | 35 M AUD, 42 M AUD |

1. The design rule runs. Its window ends at `b_start`, which is undecided, so the
   window is open. The condition is true: `b_design = "hotel"`.
2. B's rule runs. The state changed, so the executor solves again with the hotel
   Model. `b_cost` is 42 M AUD, more than the headroom. B does not start.

If the design condition were false, B's rule would read the residential cost of
35 M AUD and start B. The design rule's window would then end on that date, and
`otherwise` would fix `"residential"`. If the timing rules came first, `decide`
would reject the Specification: B's rule reads `b_cost`, which a later rule's
choice can change.

**Two provisions (cell 18, with combined Models).** The expansion is an edit that
the author applies to each B design. `a_design` is fixed, so only the expanded
combinations are reachable:

```python
def add_expansion(model):
    ...                                  # cell 17 as a function of a Model

expand = (both.alternatives(keys=("b_design", "a_design"), models={
              ("residential", "expanded"): add_expansion(residential),
              ("hotel", "expanded"): add_expansion(hotel)})
          .fix(a_design="expanded", a_provision="1.5e6 AUD")
          .decide(key="expansion_date", when="residential_index >= 1.25", review=yearly,
                  window=("a_open + 3 years", date(2035, 1, 1)), otherwise="never"))
```

**The largest justified premium (cells 13 and 14).**

```python
premiums = {p: {"provision": p} for p in ("0 AUD", "2.5e6 AUD", "5e6 AUD", "7.5e6 AUD")}
sweep = rk.execution.solve(specification=both.cases(cases=premiums).across(paths=use_paths, assign=assign))
sweep.decisions().same_across_cases()
gain = sweep.compare(other=outcomes["timing"], keys=["equity_npv"]).by_case()
gain.breakeven(key="provision", criterion="mean")
```

If the 7.5 M AUD premium stops B on some paths, `same_across_cases()` lists them
and `breakeven` raises `DecisionsChangedError`. The finance note of cell 14 then
reads the premium from the sweep table, and it states the criterion.

## Acceptance for #216

1. Both forms of `alternatives` make a Specification that pins each alternative.
   `missing_alternative`, `alternative_mismatch` and a free choice key are
   rejected. `on(model=)` is rejected with alternatives.
2. A decided choice key without `then` is rejected.
3. Lesson 07 cell 7 chooses the hotel only on paths where the condition is true
   before B starts. On every path, the realised Model is one of the two
   alternatives (cell 19).
4. The January 2030 example above runs as a unit test with a fake backend. With
   the timing rules first, `decide` raises `rule_order`.
5. An alternative whose Movements differ before the decision date fails with
   `decision_changes_past`.
6. `outcome.rollup` over a batch gives each case's rollup on its realised Model.
   On the hotel cases it agrees with a rollup of the hotel Model alone.
7. `rk.execution.compare` pairs by path, rejects different paths and counts failed
   cases. The provision is negative on every path of `switch` and `both`
   (cell 19).
8. `same_across_cases` and `breakeven` pass these tests:
   - invariant decisions give the exact premium, and it agrees with an
     independent calculation on known data;
   - changed decisions raise `decisions_changed`;
   - a key that is not affine raises `sweep_not_affine`.
9. `best` returns a tested case only, and no function searches rule parameters.
10. Lesson 07 cells 2 to 19 run on the CI path count.

## API names added

- `rk.Specification.alternatives` (both forms).
- `rk.execution.compare` and `rk.execution.StrategyComparison` with `summary` and
  `select`.
- `PairedComparison.by_case().breakeven` and `.best`.
- `rk.execution.Outcome.rollup` over a batch, and `Outcome.case(key=...).model`.
- `DecisionTable.same_across_cases`.
- `rk.errors.DecisionsChangedError`.
- Diagnostic codes: `missing_alternative`, `alternative_mismatch`,
  `decisions_changed` and `sweep_not_affine`.
- Run record field: the realised alternative of each case.

## Alternatives and consequences

- **Variants inside one Model, switched by a value.** This is the opposite of
  decision D10. Every option's structure would be in one Model, and rollups would
  need a filter for each option.
- **One choice key, with optional structure gated by a decided date.** It needs
  fewer Models, but realised rollups need a delivery date on each entity. The
  maintainer chose explicit combined Models.
- **Compose options as diffs from a common base.** It scales better, but it needs
  a diff application and a merge-conflict rule.
- **`breakeven` interpolates when decisions change.** It gives a number in all
  cases, but the number hides a changed policy. The maintainer chose to raise.
- **Solve for the premium as a target over the batch.** This is a search over a
  function that bends where decisions change. It mixes inverse solving with rules.

The Specification format changes to pin several Model revisions. This is inside the
1.0.0 format reset ([ADR-017](017-api-and-formats.md)). Lesson 07's proposed cells
change in three places: cells 7 and 15 add `then="hotel"`; cell 18 uses the combined
form; cell 14 states that `breakeven` raises when decisions change.

## Sources and related decisions

- [ADR-021: sequential decisions](021-sequential-decisions.md), which this record
  uses for rules, order, traces and pairing.
- [ADR-001: document roots](001-document-roots.md), amended by this record.
- [ADR-014: market paths](014-market-paths.md).
- [ADR-015: authoring](015-authoring.md), for `edit()` and identities.
- [ADR-020: walkthrough plan v2](020-walkthrough-plan-v2.md), lesson 07.
- Proposed cells for lesson 07 and decision D10: `examples/walkthrough/proposed/`
  (#201, [#255](https://github.com/daniel-fink/rangekeeper/pull/255)).
- Issues: [#214](https://github.com/daniel-fink/rangekeeper/issues/214) (this
  design), [#216](https://github.com/daniel-fink/rangekeeper/issues/216)
  (implementation).

Supersedes: none. Amends: ADR-001. Superseded by: none.
