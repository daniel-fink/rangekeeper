# ADR-024: Search as a query over a range of cases

Status: accepted for 1.0; implementation pending. Recorded: 2026-10-28.

## Problem

Walkthrough lesson 07 asks for the largest provision cost (the premium) that a
criterion justifies ([ADR-022](022-design-alternatives.md#the-premium-question)).
The criterion is a statistic over many solves: the mean, or the 5 % quantile, of the
paired gain across the market paths. A forward solve cannot answer this, and
[ADR-021](021-sequential-decisions.md) keeps a target over a batch out of inverse
solving.

ADR-022 designed `breakeven`, `best` and `decisions.same_across_cases()` for this.
They are special methods with their own errors. The review of the proposed cells
(#201) prefers composition, in the style of LINQ and SQL, to special functions
(decisions D30, D33 and D36). The maintainer wants a search in 1.0.

The search must not tune a rule. A trigger chosen on the paths that test it looks
better than it is (lesson 07, section 7).

## Choice

### A search is a query over a range of cases

The same query asks the question over cases that the author lists and over a range
of one value. Only the source changes. Over listed cases, the query reads solved
rows. Over a range, the engine solves only the rows that the query needs. This is
the search.

```python
# the criterion: built once, outside the query
cautious = "equity_npv.quantile(level=0.05) >= 0 AUD"

# listed cases
premiums = strategy.cases(cases={"0 AUD": {...}, "2.5e6 AUD": {...}})
# a range of one value
premiums = strategy.cases(
    cases=rk.specification.Range(key="provision", first="0 AUD", last="10e6 AUD")
)

premium_outcome = rk.execution.solve(specification=premiums.across(paths=paths))
gains = rk.execution.compare(
    outcomes={"Premiums": premium_outcome, "Timing": timing_outcome},
    keys=["equity_npv"],
    baseline="Timing",
).by_case
largest = gains.where(condition=cautious).max(key="provision", tolerance="50e3 AUD")
```

- **`cases=` takes a mapping or a `Range`.** A mapping gives named cases. A
  `Range(key=, first=, last=)` gives the cases of one value between two bounds; each
  case is named by its value. There is one `cases` call, and `by_case` works in the
  same way for both.
- **A range is deferred.** `solve` on a range returns an Outcome that has no solved
  rows yet. A final operation (`max`, `min`, `first`) runs the solves that it needs,
  as `Max()` runs a LINQ query. An operation that needs every row of a range, such
  as `summary()`, raises `ValidationError` with the code `range_not_materialised`.
- **The criterion is a value.** It is condition text, or the same condition in the
  Python form of [ADR-015](015-authoring.md#equations)
  (`rx.key("equity_npv").quantile(level=0.05) >= "0 AUD"`). The author defines it
  once and injects it into each query. Statistics are methods on a compared key:
  `mean()`, `quantile(level=)`, `share_better()`, `min()` and `max()`.

### The by-case table is a query

`by_case` returns a table with one row for each case: the case's values (for
example `provision`) and the statistics of each compared key. It has these
operations:

| Operation | Result | Over a range |
| --- | --- | --- |
| `where(condition=)` | The rows that meet the condition | Deferred |
| `order_by(key=, descending=False)` | The rows in order | Deferred |
| `first()` | One row | Runs the solves |
| `max(key=, tolerance=None)`, `min(key=, tolerance=None)` | The largest or smallest value of `key` among the rows | Runs the solves; `tolerance` is required |
| `summary()` | All rows | Raises `range_not_materialised` |
| `explain()` | The plan: the method and the solves that it needs | Runs no solve |

"Best tested" is a query: `by_trigger.order_by(key="equity_npv.mean()",
descending=True).first()`. `best`, `breakeven`, `same_across_cases`,
`rk.execution.Criterion`, `DecisionsChangedError` and the codes `decisions_changed`
and `breakeven_not_affine` are removed.

### The plan

For `max` or `min` over a range, the engine plans in this order:

1. **Exact.** It solves the two bounds. If no decided value differs between them, a
   third solve checks that each path's compared value is linear in the varied value.
   The engine then computes the answer exactly: for a mean, from the two means; for a
   quantile, by sorting the points where each path's line crosses the condition.
   This is three batch solves.
2. **Bracketed.** Otherwise, the engine halves the bracket between the last value
   that meets the condition and the first that does not, until the bracket is
   narrower than `tolerance`.
3. **Not unique.** If the condition changes more than once between tested values,
   the result says that the answer may not be unique, and gives every change.

The result carries its evidence: `value`, `method` (`exact` or `bracketed`),
`bracket`, and `tested`, which is the by-case table of every solved value. The Run
records the tested cases, the method and the bracket. Replay solves the same cases
and compares the result.

### A range cannot vary a value that a rule reads

```python
strategy.cases(
    cases=rk.specification.Range(key="start_trigger", first=1.00, last=1.20)
)
# ValidationError(code="range_over_rule_input"): start_trigger is read by the rule
# that decides start_date. Searching it tunes the rule on these paths. Test several
# triggers as listed cases, and check the chosen one on new paths.
```

`cases` checks this when the range is written, before any solve. The rule covers
every value that a rule reads: a trigger, and any value that a condition observes.
Listed cases of such a value stay allowed.

## Alternatives and consequences

- **A search function, such as `rk.execution.search(...)`.** It works, but it is a
  second way to ask the question that a query asks, and its arguments hide the
  criterion inside a call. The maintainer prefers composition.
- **A range as its own method, such as `spec.vary(...)`.** A reader already knows
  cases and `by_case`. A range is another source of cases, so it is an argument
  of `cases`.
- **`breakeven` with a straight-line fit.** It gives an exact premium only when
  decisions do not change, and it needs its own error class. The plan's exact step
  does the same work inside the query.
- **Allow a range over a trigger.** This would make policy search easy and
  over-fitting likely. The refusal names the alternative: listed cases and new paths.
- **Interpolate between listed cases.** The query over listed cases answers from the
  tested rows only, as "best tested" did in ADR-022.

Users write one query for listed cases and for a range. Lesson 07 composes the mean
premium by hand from two runs, to teach the finance, and uses the query for the 5 %
quantile. #216 implements the range, the deferred Outcome, the case-table operations,
the plan and the refusal, with tests for each step of the plan and for replay.

## Sources and related decisions

- [ADR-021: decide values by rules](021-sequential-decisions.md), amended: a
  search over a range of one Specification value joins simulation and inverse
  solving; policy search stays out.
- [ADR-022: design alternatives](022-design-alternatives.md), amended: the premium
  question and "best tested" become queries.
- [ADR-015: authoring](015-authoring.md#equations), for condition text and `rx`.
- Proposed cells for lesson 07 and decisions D30, D33, D36 and D37:
  `examples/walkthrough/proposed/` (#201,
  [#255](https://github.com/daniel-fink/rangekeeper/pull/255)).

Supersedes: none. Superseded by: none. Amends: ADR-021, ADR-022.
