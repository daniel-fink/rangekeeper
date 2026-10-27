# ADR-022: Choose between design alternatives with rules

Status: accepted for 1.0; implementation pending. Recorded: 2026-10-27. Amended
2026-10-27 by #201 decisions D2, D24, D25 and D26 (reviews as `Periods`, `NEVER`,
enums, keyed members in rule text, the equity-first funding names). Amended
2026-10-28 by [ADR-024](024-search-as-query.md): the premium question and "best
tested" are queries; `breakeven`, `best` and `same_across_cases` are removed.

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
  expansion floor when `expansion_date` is `NEVER`, is still in the realised
  Model. Report its delivery through its dated Flows and the decided date. A
  rollup that knows about delivery dates is not in 1.0.

### Paired comparison of strategies

`rk.execution.compare(outcomes={name: outcome, ...}, keys=, baseline=)` returns the
`Comparison` of [ADR-021](021-sequential-decisions.md). The same call compares two
strategies or more (decision D30 of #201):

- All Outcomes must pin the same `rk.market.Paths`. If not, it raises
  `different_market_paths`.
- It pairs each strategy with the baseline by path member key. Strategies can use
  different alternatives.
- It has `summary()` and `select(*names)`.
- A provision is a fixed value in every alternative of a strategy. Its cost is in
  every path, also where the option is never used. The comparison needs no special
  rule for it.

### The premium question

The provision is paid from equity, so it reduces the available equity. A rule
such as `equity_available + loan_available >= b_cost` can then decide differently
as the premium rises. The library makes this visible and does not hide it:

- **Test several premiums as cases:** `cases(cases=premiums)`, with one case for each
  premium written out (decision D24 of #201), across the paths.
- **Ask for the largest justified premium as a query**
  ([ADR-024](024-search-as-query.md)). The criterion is a condition, for example
  `"equity_npv.quantile(level=0.05) >= 0 AUD"`. Over listed premiums,
  `by_case().where(condition=...).max(key="provision")` gives the largest tested
  premium. Over a `Range` of `provision`, the same query searches: it is exact
  when no decision changes and the gains are linear in the premium, and bracketed
  otherwise. If the condition changes more than once, the result says that the
  answer may not be unique.

### Kept apart from optimisation

- A choice key cannot be free. The library has no objective over alternatives.
- "Best tested" is a query over listed cases:
  `by_case().order_by(key="equity_npv.mean()", descending=True).first()`
  ([ADR-024](024-search-as-query.md)).
- To test triggers on new paths, `Paths.regenerate(seed=)` rebuilds the
  generator from the capture record (#201 gap G69). A new seed gives a test set. Nothing in
  the library tunes a trigger: a range cannot vary a value that a rule reads
  (ADR-024).

## Worked examples

These come from the proposed cells of lesson 07 (#201). Amounts are illustrative.

**A rule chooses the design (cell 7, with `then`).**

```python
switch = (
    fixed.alternatives(b_design={"residential": residential, "hotel": hotel})
    .fix(provision="2.5e6 AUD")
    .parameters(switch_trigger=1.10)
    .decide(
        key="b_design",
        when='use_index["hotel"] >= switch_trigger * use_index["residential"]',
        periods=design_reviews,
        earliest="shared_start + 1 year",
        latest="b_start - 1 year",
        then="hotel",
        otherwise="residential",
    )
)
both = switch.with_rules(rules=timing)  # start_date, b_start, b_sale_date follow
```

`design_reviews` and, below, `expansion_reviews` are `rk.duration.Periods`, as in
lesson 07. A rule reads one member of the keyed `use_index` by name.

**The design before the start, on one date.** In `both`, the design rule is
written first. In January 2030 on one path:

| Observed | Value |
| --- | --- |
| `use_index["hotel"] >= 1.10 * use_index["residential"]` | true |
| `rent_index >= 1.10` | true |
| `equity_available + loan_available` | 40 M AUD |
| `b_cost` as residential, as hotel | 35 M AUD, 42 M AUD |

1. The design rule runs. Its `latest` bound refers to `b_start`, which is
   undecided, so the review is open. The condition is true: `b_design = "hotel"`.
2. B's rule runs. The state changed, so the executor solves again with the hotel
   Model. `b_cost` is 42 M AUD, more than the available equity and loan. B does
   not start.

If the design condition were false, B's rule would read the residential cost of
35 M AUD and start B. The design rule's `latest` bound would then have passed, and
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
          .decide(key="expansion_date", when='use_index["residential"] >= 1.25',
                  periods=expansion_reviews, earliest="a_open + 3 years",
                  otherwise=rk.duration.NEVER))
```

**The largest justified premium (cells 13 to 14b, and exercise 2).** The cells
compose the mean premium from two runs, to teach the finance: the mean paired gain
without the premium, divided by what each dollar of premium costs, and one more solve
at that premium to check it. Exercise 2 asks for the 5 % quantile criterion as a
query over a range:

```python
cautious = "equity_npv.quantile(level=0.05) >= 0 AUD"
premiums = both.cases(
    cases=rk.specification.Range(key="provision", first="0 AUD", last="10e6 AUD")
)
premium_outcome = rk.execution.solve(
    specification=premiums.across(paths=use_paths, series=use_series)
)
gains = rk.execution.compare(
    outcomes={"Premiums": premium_outcome, "Timing": strategy_outcomes["timing"]},
    keys=["equity_npv"],
    baseline="Timing",
).by_case()
largest = gains.where(condition=cautious).max(key="provision", tolerance="50e3 AUD")
largest.value, largest.method, largest.bracket
```

If the premium changes a decision on some paths, the plan is bracketed, and
`largest.tested` shows each tested premium.

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
8. The premium queries of [ADR-024](024-search-as-query.md) pass its tests: the
   exact plan agrees with an independent calculation on known data, and a changed
   decision gives a bracketed plan.
9. "Best tested" returns a tested case only, and a range over a rule's input is
   refused.
10. Lesson 07 cells 2 to 19 run on the CI path count.

## API names added

- `rk.Specification.alternatives` (both forms).
- `rk.execution.compare` and `rk.execution.Comparison` (shared with ADR-021).
- The by-case table and its queries ([ADR-024](024-search-as-query.md)).
- `rk.execution.Outcome.rollup` over a batch, and `Outcome.case(key=...).model`.
- Diagnostic codes: `missing_alternative` and `alternative_mismatch`.
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
- **A `breakeven` method.** It interpolated between premiums and raised when
  decisions changed. [ADR-024](024-search-as-query.md) replaces it with a query,
  which is exact when decisions do not change and bracketed when they do.

The Specification format changes to pin several Model revisions. This is inside the
1.0.0 format reset ([ADR-017](017-api-and-formats.md)). Lesson 07's proposed cells
change in three places: cells 7 and 15 add `then="hotel"`; cell 18 uses the combined
form; cells 13 to 14b compose the premium, and exercise 2 queries it (ADR-024).

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
