# ADR-021: Decide values by rules over market paths

Status: accepted for 1.0; implementation pending. Recorded: 2026-10-27. Amended
2026-10-27 by #201 decisions D2, D25 and D26 (`Periods`, `NEVER`, the equity-first
funding names), and 2026-10-28 by decisions D41 (rules, not policies) and D42 (a rule
is a query over a window).

## Problem

Walkthrough lesson 05 asks when to buy the site, start Building B or stop
([ADR-020](020-walkthrough-plan-v2.md#05-when-to-commit)). Its proposed cells
(#201) need three timing options on lesson 04's market paths:

- **wait to start:** start when an observed market value reaches a trigger;
- **conditional start of Building B:** start B only when the market and the
  funding allow it, before a latest date;
- **abandon:** if B has not started by a date, sell B's share of the site.

The current library cannot do this:

- **The policy slice is exogenous.** `specification.policy.evaluate` runs once,
  before compilation, on recorded values. It rejects a solved observation, such as
  the available loan ([scenarios and policies](../reference/scenarios-and-policies.md)).
- **It has an action concept.** Decision D9 of #201 removes it: if a value can
  change, it belongs in the Specification; if it is part of the modelling, it
  belongs in the Model. A rule decides one value. There is no action.
- **ADR-013 has no design for this.** Its stage 3 says "evaluate policies at their
  decision dates", but it does not say how a rule reads a solved value.
- **ADR-014 left two points open (#139):** how availability attaches to case
  assignments, and how a case refers to a path member.

The design must keep the solve pure ([ADR-013](013-execution-and-extensions.md))
and the backend affine. It must keep simulation, inverse solving and rule tuning
apart.

## Choice

### Terms

| Term | Meaning | Name |
| --- | --- | --- |
| Rule | A query that fixes one value during the solve: the first date in a window when a condition holds, or a default | `rk.specification.Rule` (made by a query, not by hand) |
| Window | The dates on which a rule may act, with optional bounds | `rk.specification.Window` |
| Window date | One date in a window, on which the rule checks its condition | — |
| Decided | A role beside fixed and free. A rule fixes the value on a date | `rk.specification.Role.DECIDED` |
| Decision date | The window date on which a rule fixed its value | `decision_date` |
| Observation | A value that a rule reads, with the date it became available | `Observation` |
| Decision trace | The record of each window date and its result, in the Run | `rule_evidence` |
| Rules | All the rules of one Specification, in order; a Specification with rules is a strategy | `Specification.rules` |

### Write a rule

A rule is a query over a window of dates, composed in the style of LINQ's
`Where(...).FirstOrDefault(...)` and SQL's `COALESCE(MIN(date) WHERE ..., default)`
(decision D42 of #201):

```python
window = rk.specification.Window(earliest=date(2027, 1, 1), latest=date(2030, 1, 1))
rule = window.where(condition="rent_index >= start_trigger").first(
    otherwise=rk.duration.NEVER
)
strategy = fixed.parameters(start_trigger=1.05).fix(start_date=rule)
```

- **`Window(earliest=None, latest=None, periods=None, timing=PeriodTiming.FIRST)`**
  gives the window dates. With no `periods`, a window date is each date on which a
  value that the condition reads becomes available. With `periods`, it is the first
  day of each Period (`timing=PeriodTiming.LAST` moves it to the last day).
  `earliest` and `latest` are inclusive bounds. Each is a date or an expression, such
  as `"shared_start + 1 year"` or `"b_start - 1 year"`.
- **`where(condition=...)`** takes a condition in the equation language. It can use
  comparisons, `and`, `or`, `not` and `NEVER`. Its names are Model values,
  Specification parameters and values that earlier rules decide.
- **`first(otherwise=..., then=None)`** gives the rule. On each path, the rule fixes
  its value on the first window date on which the condition holds: the date itself,
  or `then` when the value is not a date (a choice key,
  [ADR-022](022-design-alternatives.md)).
  If no window date qualifies, the value is `otherwise`. For a date it can be
  `rk.duration.NEVER`, written `NEVER` in condition text.
- **`fix(key=rule)`** makes the value decided. A later `fix` of the same key replaces
  the earlier one, rule or quantity, in the same position. Rules run in the order in
  which they are fixed.

Two more Specification members support rules:

- `parameters(**values)` declares named Specification values for rules, such as a
  trigger. `fix` and cases change them like other values, and a rule can read them
  on every window date.
- `rules` returns the rules by key, in their order. `rules[key]` is a rule with the
  parameters that it reads, so a strategy can reuse it:
  `fixed.fix(start_date=timing["start_date"])`.

`free(key)` on a decided value removes its rule.

### What a rule can observe

A rule reads the value that is available on the window date. A Flow name in a
condition reads the latest available Movement. `x.shift(by=1)` reads the
Movement before it.

| Source | Available on the window date when |
| --- | --- |
| A path Flow that `across` assigns | Its availability date is on or before the window date. A period Movement is available at the period's `end` plus the output's lag; a dated Movement at its date plus the lag ([ADR-014](014-market-paths.md)) |
| A fixed value or a rule parameter | Always |
| A value that an earlier rule decided | Its decision date is on or before the window date |
| A solved Flow, such as `loan_available` | Its Movement is in a period that ends on or before the window date |
| A solved scalar, such as `b_cost` | It does not depend on a free input, on a value that a later rule decides, or on a Movement that is not yet available |

Two rules apply to undecided values:

- **A direct reference to an undecided value is unknown.** For example,
  `b_start == NEVER` is unknown until B's rule decides. A check fixes its value
  only when the condition is true; unknown is not true. The trace records the
  observation as undecided.
- **A solved value uses the current state.** Undecided values take their
  `otherwise` value in the provisional solve. A direct reference asks about the
  decision; a solved value asks about the project as it stands now.

Validation rejects a rule that reads the future. It checks in two places:

1. **When the Specification is made.** `fix` rejects a rule with a look-ahead in the
   condition text, such as `rent_index.shift(by=-1)`, with
   `AvailabilityError`. It also rejects these conditions:
   - a condition that refers to a value that a later rule decides, or reads a
     solved scalar that depends on one (code `rule_order`);
   - a condition that reads a free input (code `rule_reads_unknown`).
2. **During the solve.** The executor checks each observation. An unavailable
   observation fails that case with the code `observation_unavailable`. Other
   cases continue.

### State and commitments

- **State.** For each path, the state is the decided values with their decision
  dates, and the provisional solution.
- **The provisional solution** fixes the decided values and gives each undecided
  value its `otherwise` value.
- **Decisions are final.** A rule decides once. Nothing reverses a decision.
  Abandonment is a separate decided value that the Model relates to the plan,
  such as `b_sale_date`.
- **Commitments belong to the Model.** Equations compose them from `cumulative()`,
  `total()` and `since(on=b_start)` (decision D2 of #201). When a rule decides
  `b_start`, `committed` includes B's budget from that date. The executor adds no
  commitment of its own.
- **Funding feasibility is part of the condition.** The author writes it, for
  example `equity_available + loan_available >= b_cost`. The executor does not
  block a decision that makes the commitment gap positive. The commitment gap is a
  Model value, and the Outcome reports it (lesson 05, exercise 2).

### Evaluation order

The executor evaluates each path on its own. It processes each window date, and
the date after each rule's last window date, in date order:

1. **Rules run in the order they are written.** Each rule sees the state at the
   moment it runs. This includes decisions by earlier rules on the same date.
2. **A window date is open** when its `earliest` bound is decided and on or before
   the date, and its `latest` bound is undecided or on or after the date. An
   `earliest` bound that refers to an undecided value keeps the window closed. A
   `latest` bound that refers to an undecided value keeps them open.
3. **When a rule runs:**
   - if its last window date has passed (its Periods have ended, or its `latest` bound
     is before the date), it fixes `otherwise` on this date;
   - if the date is an open window date, it tests the condition. If the condition
     is true, it fixes `then` (or the date) on this date.
4. **Before a rule reads a solved value,** the executor solves the provisional
   problem again if the state changed since the last solve.
5. **After all rules on the date,** each undecided rule whose last window date has now
   passed fixes `otherwise` on this date. An `earliest` bound that becomes `NEVER`
   also closes the window dates.
6. **At the end of its last Period,** each undecided rule fixes `otherwise` on that
   date. (A Model has no timeline of its own, decision D20 of #201.)
7. **Finally,** the executor solves once with every decided value fixed. Then it
   makes the candidate, verifies it and assembles the Outcome.

**Decisions do not change the past.** A decision on a date must not change a
Movement before that date. The executor compares each new provisional solution, and
the final candidate, with the earlier one. A change fails the case with the code
`decision_changes_past`. The diagnostic names the decision and the Movement. For
example, a Model relation `marketing_start = b_start - 6 months` fails this check.

### The affine pipeline

This record amends stage 3 of [ADR-013](013-execution-and-extensions.md):

- **Bind roles** gives each value its role, including decided. It does not
  evaluate rules.
- **A new stage, rules,** follows it when the Specification has rules. For each
  path, it runs the evaluation order. It calls build problem and solve (stages 4
  and 5) for each provisional solve. It returns the decided values and the trace.
  The stage is the pure function
  `rangekeeper.execution.run_rules(composition, *, backend, config) -> Decisions`.
- **Stages 4 to 8 then run once** with the decided values fixed. The affine
  problem never contains a rule: a decided value is a fixed value in it.

Rules that read only path Flows, fixed values, parameters and decided values need
no provisional solve. Then each path has one solve. A rule that reads a solved
value adds at most one solve for each decision before it. Worker reuse
([#130](https://github.com/daniel-fink/rangekeeper/issues/130)) keeps this cost
low.

An infeasible provisional solve fails that case. The diagnostic names the window
date, the decided values and the broken constraint (lesson 05, cell 7).

### Simulation, inverse solving and search stay apart

- **Simulation** is this record: a forward solve with rules.
- **Inverse solving.** A Specification with rules can have free inputs only when
  no observation depends on them. Each path then solves its free inputs with its
  final decisions. There is no target over a batch, such as a mean.
- **Search over a range of one value** is a query over a range of cases
  ([ADR-024](024-search-as-query.md)). A range cannot vary a value that a rule
  reads.
- **Rule tuning** is not in the library. Several values of a rule parameter are a
  set of listed cases, and cases multiply with paths. "Best tested" is a query over
  those cases (ADR-024).

### Decision traces in the Run

The Run report has a `rule_evidence` section. For each case it records:

- **`checks`:** one record for each window date and each `otherwise`. A record has
  the rule key, the date, the observations, the condition result (true, false or
  unknown), the result as an `rk.execution.DecisionResult` (decided, not met,
  skipped or otherwise) and the decided value.
- **Observations:** name, reference, quantity, availability date and source (path,
  fixed, parameter, decided or solved).
- **`decided`:** for each key, the value, the decision date and the rule.
- **`verified`:** the result of the trace check, with its diagnostics.

The `Outcome` reads the trace:

- `outcome.decisions` returns a table with one row for each case and window date. It
  has `where(key=, result=)` and `observations`.
- `outcome.case(key=...).trace` shows the window dates of one case.
- Decided values appear in `outcome.table(...)` like other values.

The new `Rule`, `Check` and `RuleEvidence` records replace `Decision`,
`Action` and `DecisionOutcome`. `ObservedQuantity` stays.

### Verification and replay

- **The trace check** is the independent verification of rules
  ([ADR-003](003-computation-and-evidence.md)). It runs after each solve, and on a
  stored Run without a solve. It checks:
  - the dates, the windows and their bounds, the written order and each
    observation's availability;
  - that each condition result follows from the recorded observations;
  - that each value is fixed on the first window date where the condition holds,
    or `otherwise` on the correct date;
  - that the candidate contains the decided values;
  - that path observations equal the path data;
  - that solved Flow observations equal the candidate's Movements.
- **Replay.** `rk.execution.replay(run=, store=)` solves again from the pinned
  Specification and market paths (`rk.market.Paths`). It compares the new trace
  with the stored trace.
  The decisions and dates must be the same, and the values must agree within
  tolerance. A difference gives the diagnostic `replay_mismatch`, which names the
  first window date that differs.

### Paired comparison

`rk.execution.compare(outcomes={name: outcome, ...}, keys=, baseline=None)` returns
a `Comparison`. It is the one call for two Outcomes or more (decision D30 of #201):

- Without `baseline`, it shows the values of the keys side by side.
- With `baseline`, all Outcomes that hold paths must pin the same `rk.market.Paths`.
  If not, `compare` raises `ValidationError` with the code `different_paths`.
- It pairs cases by path member key. If one Outcome has cases across paths and the
  other has only paths, it pairs each case with the same path in the other.
- It gives the difference from the baseline for each path and key. It has `summary()` (mean
  difference, share of paths better, worst loss and 5 % quantile), `by(key=)`,
  `by_case` and `where(**values)`.
- A failed case is not in the differences. `summary()` gives the count of failed
  cases.

### Removed

- `Policy`, `Decision`, the old `Rule`, `Action`, `ActionKind`, `DecisionOutcome`,
  `evaluate` and `observe` leave `specification.policy`.
- The exact Boolean evaluator and the availability rule move into `execution` as
  internal modules.
- The investment resale example fixes `sale_date` with a rule.

## Worked examples

These come from the proposed cells of lesson 05 (#201). Market values are
illustrative.

**Wait to start (cell 6).**

```python
start_window = rk.specification.Window(
    earliest=date(2027, 1, 1), latest=date(2030, 1, 1)
)
start_rule = start_window.where(condition="rent_index >= start_trigger").first(
    otherwise=rk.duration.NEVER
)
wait = fixed.parameters(start_trigger=1.05).fix(start_date=start_rule)
```

| Date | Kind | Period read | `rent_index` | Condition | Result |
| --- | --- | --- | --- | --- | --- |
| 2027-01-01 | check | 2026 | 1.00 | false | — |
| 2028-01-01 | check | 2027 | 0.97 | false | — |
| 2029-01-01 | check | 2028 | 0.95 | false | — |
| 2030-01-01 | check | 2029 | 1.06 | true | `start_date = 2030-01-01` |

The window dates are the dates on which a new rent index becomes known: each
January, when the year before ends. Each check reads the period that ended on that
date. The path must therefore include the period before the first window date. If it
does not, the first check fails with `observation_unavailable`. The rule reads only
a path Flow, so
each path has one solve. On this path, B's
fixed start in 2030 is before the shared works finish. The case fails, and the
diagnostic names the constraint `b_start >= shared_start + 1 year` (cell 7). On a
path that never passes 1.05, the last window date (2030-01-01) passes and the rule fixes
`NEVER`.

**A look-ahead (cell 8).** The condition `"rent_index.shift(by=-1) >= 1.05"` reads
the next period. `fix` raises `AvailabilityError` before any solve. The error has `code`,
`key`, `available_on` and `decision_date`.

**Start Building B with a funding check (cell 9).**

```python
b_window = rk.specification.Window(
    earliest="shared_start + 1 year", latest=date(2032, 1, 1)
)
b_rule = b_window.where(
    condition="rent_index >= b_start_trigger and equity_available + loan_available >= b_cost"
).first(otherwise=rk.duration.NEVER)
start_b = wait.parameters(b_start_trigger=1.10).fix(b_start=b_rule)
```

The window dates stay closed until `start_date` is decided, because `earliest` refers to
it. `equity_available` and `loan_available` are solved Flows. On each window date, the
executor uses the provisional solution with `start_date` fixed and `b_start` at
`NEVER`. After `start_date` is decided, the
first window date of B solves again, and later window dates reuse that solution until a
decision changes the state. On 2031-01-01 the rule reads both at the end of the
2030 period.

**Abandon (cell 11).** The rule for `b_sale_date` reads `b_start == NEVER`.
`b_start` is fixed first. On 2033-01-01, B's rule runs first: its last window date
has passed, so it fixes `NEVER`. Then the sale rule runs. Its window, 2033-01-01, is
open, and its condition is true. If the sale rule were fixed first, `fix` would
reject it with `rule_order`.

**Several triggers (cell 17).** The trigger is a Specification parameter from
cell 6. `cases` make one case for each trigger, across every path. Each case key is
a pair of the
case name and the path member key ([ADR-014](014-market-paths.md)).

## Acceptance for #215

1. `Window`, `where` and `first` make rules; `fix`, `parameters` and `rules` work
   with them and return new Specifications. A replaced rule keeps its position.
2. `fix` raises `AvailabilityError` for cell 8. It raises `ValidationError`
   with `rule_order` for a reference to a later rule, and with
   `rule_reads_unknown` for an observation that depends on a free input.
3. Unit tests with a fake backend, and no subprocess, cover each step of the
   evaluation order:
   - rules on the same date, and the written order;
   - the last window date passing when the rule runs, and after the date;
   - undecided `earliest` and `latest` bounds and unknown comparisons;
   - the end of the last Period.
4. A rule set that reads only path values runs one solve for each path. A rule
   set with a funding observation stays within the stated solve bound. The Run
   report records the solve count for each case.
5. A Model with `marketing_start = b_start - 6 months` fails with
   `decision_changes_past`.
6. The trace check passes for each lesson 05 case. Each observation has
   `available_on <= decision_date` (cell 18). A changed trace fails the check.
7. Replay gives the same trace. Replay against changed path data gives
   `replay_mismatch`.
8. `compare` raises `different_paths` for different paths. It pairs
   cases across paths, and `summary()` counts failed cases.
9. Lesson 05 cells 5 to 18 run on the three histories and on the CI path count.
   On the three histories, the decisions and equity NPVs agree with an
   independent calculation of the rules on known data.
10. The old policy slice is removed, and the investment example and its tests use
    rules. The [scenario reference](../reference/scenarios-and-policies.md) and
    the glossary describe the new terms.

## API names added

- `rk.specification.Window` with `where` and `first`; `rk.Specification.fix` with a
  rule, `.parameters` and `.rules`.
- `rk.specification.Rule` and `rk.specification.Role`.
- `rk.duration.Periods` and `rk.duration.NEVER` (decisions D25 and D26 of #201).
- `rk.execution.DecisionResult`.
- `rk.execution.run_rules` and `rk.execution.Decisions` (stage).
- `rk.execution.Outcome.decisions` and `Outcome.case(key=...).trace`.
- `rk.execution.compare` (shared with [ADR-022](022-design-alternatives.md)).
- `rk.execution.Comparison` with `summary`, `by`, `by_case`, `where` and `select`.
- `rk.errors.AvailabilityError`.
- Diagnostic codes: `rule_order`, `rule_reads_unknown`,
  `observation_unavailable`, `decision_changes_past`, `replay_mismatch` and
  `different_paths`.
- Run records: `RuleEvidence`, `Check` and `Observation`.

## Alternatives and consequences

- **Evaluate rules once before the solve.** This keeps one solve for each path,
  but a rule cannot read funding. Lesson 05 cell 9 and exercise 2 would change.
- **Solve a truncated problem up to each window date.** Each solve is smaller,
  but every Model would have to be truncatable. NPV, IRR and reversion use the
  whole timeline.
- **One mixed-integer problem with a binary variable for each window date.** This is
  optimisation, not simulation, and the backend would not be affine.
- **Let the executor sort rules by their references.** The order would not show in
  the Specification. Lesson 07's design and start rules make a cycle that the
  executor would have to reject.
- **A `decide(key=, when=, periods=, earliest=, latest=, then=, otherwise=)`
  method, or a `Rule` object added with `with_rules`.** Both give eight arguments to
  one call, or a third structure beside `fix` and queries. A rule written as a query
  (`Window(...).where(...).first(...)`) reuses `where`, `condition=` and `first` from
  the query API (#201, decision D42).
- **A window tuple with a review frequency** (`review=yearly, window=(start, end)`).
  The reader must remember the order and that the end is excluded.
- **Block decisions that the funding cannot cover.** This hides a modelling choice
  in the executor. Lesson 05 shows the commitment gap when the check is missing.
- **Keep the action concept.** Decision D9 of #201 removes it. A rule decides one
  value, and the Model relates the other dates to it.

The rule API replaces the current policy API. This is a breaking change inside the
1.0.0 format reset ([ADR-017](017-api-and-formats.md)). Lesson 05's proposed cells
write each rule as a query over a window. The rename pass
([ADR-012](012-naming-and-glossary.md)) does not change these names.

## Sources and related decisions

- [ADR-013: execution and extension points](013-execution-and-extensions.md),
  amended by this record for stage 3 and the rules stage.
- [ADR-014: market paths](014-market-paths.md), amended by this record for
  availability and member references (#139).
- [ADR-022: design alternatives](022-design-alternatives.md), which uses these
  rules to choose a design.
- [ADR-020: walkthrough plan v2](020-walkthrough-plan-v2.md), lesson 05.
- Proposed cells for lesson 05 and decisions D2, D8, D9, D25 and D26:
  `examples/walkthrough/proposed/` (#201,
  [#255](https://github.com/daniel-fink/rangekeeper/pull/255)).
- [Scenarios and policies reference](../reference/scenarios-and-policies.md), which
  changes when #215 lands.
- Issues: [#213](https://github.com/daniel-fink/rangekeeper/issues/213) (this
  design), [#215](https://github.com/daniel-fink/rangekeeper/issues/215)
  (implementation), [#139](https://github.com/daniel-fink/rangekeeper/issues/139).

Supersedes: none. Amends: ADR-013, ADR-014. Superseded by: none.
