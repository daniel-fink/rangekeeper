# ADR-021: Decide values by rules over market paths

Status: accepted for 1.0; implementation pending. Recorded: 2026-10-27.

## Problem

Walkthrough lesson 05 asks when to buy the site, start Building B or stop
([ADR-020](020-walkthrough-plan-v2.md#05-when-to-commit)). Its proposed cells
(#201) need three timing options on lesson 04's market paths:

- **wait to start:** start when an observed market value passes a threshold;
- **conditional start of Building B:** start B only when the market and the
  funding allow it, before a latest date;
- **abandon:** if B has not started by a date, sell B's share of the site.

The current library cannot do this:

- **The policy slice is exogenous.** `specification.policy.evaluate` runs once,
  before compilation, on recorded values. It rejects a solved observation, such as
  funding headroom ([scenarios and policies](../reference/scenarios-and-policies.md)).
- **It has an action concept.** Decision D9 of #201 removes it: if a value can
  change, it belongs in the Specification; if it is part of the modelling, it
  belongs in the Model. A rule decides one value. There is no action.
- **ADR-013 has no design for this.** Its stage 3 says "evaluate policies at their
  decision dates", but it does not say how a rule reads a solved value.
- **ADR-014 left two points open (#139):** how availability attaches to case
  assignments, and how a case refers to a path member.

The design must keep the solve pure ([ADR-013](013-execution-and-extensions.md))
and the backend affine. It must keep simulation, inverse solving and policy search
apart.

## Choice

### Terms

| Term | Meaning | Name |
| --- | --- | --- |
| Rule | A Specification declaration that decides one value during the solve | `Rule` |
| Decided | A role beside fixed and free. A rule fixes the value on a date | role `decided` |
| Review date | A date on which a rule tests its condition | — |
| Window | The half-open range `[start, end)` that contains the review dates | `window=` |
| Decision date | The date on which a rule fixed its value | `decision_date` |
| Observation | A value that a rule reads, with the date it became available | `Observation` |
| Decision trace | The record of each review and its result, in the Run | `policy_evidence` |
| Policy | All the rules of one Specification, in order | `Specification.rules` |

### Declare a rule

`Specification.decide(key, *, when, review, window, otherwise, then=None)` returns
a new, immutable Specification (decision D8 of #201).

- **`key`** names a Model value, or a choice key ([ADR-022](022-design-alternatives.md)).
  Its role becomes decided. `decide` replaces an earlier fix of the same key. If
  the key already has a rule, `decide` replaces that rule in the same position.
- **`when`** is a condition in the equation language. It can use comparisons,
  `and`, `or`, `not` and `never`. Its names are Model values, Specification
  parameters and values that earlier rules decide.
- **`review`** is a `Frequency`. Review dates start at the window start and step
  by the frequency.
- **`window=(start, end)`** is half-open, like a Period: the end is not a review
  date. Each bound is a date or an expression, such as `"shared_start + 1 year"`
  or `"b_start"`.
- **`then`** is the value that the rule fixes when the condition is true. For a
  date value, the default is the review date. For any other value, `then` is
  required.
- **`otherwise`** is the value when no review is true. For a date value it can be
  `never` (#201 gap G50).

Three more Specification members support rules:

- `parameters(**values)` declares named rule parameters, such as a threshold.
  Cases can change them, and a rule can read them on every review date.
- `rules` returns the rules in their order, as `Rule` records.
- `with_rules(rules=...)` adds rules after the existing rules. A rule for a key
  that already has a rule replaces it in the same position.

A value cannot be both fixed and decided. `free(key)` on a decided value removes
its rule.

### What a rule can observe

A rule reads the value that is available on the review date. A Flow name in a
condition reads the latest available Movement. `shift(flow=x, periods=1)` reads
the Movement before it.

| Source | Available on the review date when |
| --- | --- |
| A path Flow that `across` assigns | Its availability date is on or before the review date. A period Movement is available at the period's `end` plus the output's lag; a dated Movement at its date plus the lag ([ADR-014](014-market-paths.md)) |
| A fixed value or a rule parameter | Always |
| A value that an earlier rule decided | Its decision date is on or before the review date |
| A solved Flow, such as `funding.headroom` | Its Movement is in a period that ends on or before the review date |
| A solved scalar, such as `b_cost` | It does not depend on a free input, on a value that a later rule decides, or on a Movement that is not yet available |

Two rules apply to undecided values:

- **A direct reference to an undecided value is unknown.** For example,
  `b_start == never` is unknown until B's rule decides. A review fixes its value
  only when the condition is true; unknown is not true. The trace records the
  observation as undecided.
- **A solved value uses the current state.** Undecided values take their
  `otherwise` value in the provisional solve. A direct reference asks about the
  decision; a solved value asks about the project as it stands now.

Validation rejects a rule that reads the future. It checks in two places:

1. **When the Specification is made.** `decide` rejects a look-ahead in the
   condition text, such as `shift(flow=rent_index, periods=-1)`, with
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
- **Commitments belong to the Model.** An account declares them, for example
  `commitments={"b_works": "b_start"}` (decision D2 of #201). When a rule decides
  `b_start`, the account's committed amount includes B's budget from that date.
  The executor adds no commitment of its own.
- **Funding feasibility is part of the condition.** The author writes it, for
  example `funding.headroom >= b_cost`. The executor does not block a decision
  that makes the commitment gap positive. The commitment gap is a Model value, and
  the Outcome reports it (lesson 05, exercise 2).

### Evaluation order

The executor evaluates each path on its own. It processes each review date and
each known window end, in date order:

1. **Rules run in the order they are written.** Each rule sees the state at the
   moment it runs. This includes decisions by earlier rules on the same date.
2. **A window is open** when its start is decided and on or before the date, and
   its end is undecided or after the date. A start that refers to an undecided
   value is closed. An end that refers to an undecided value is open.
3. **When a rule runs:**
   - if its window end is on or before the date, it fixes `otherwise` on this date;
   - if its window is open and the date is a review date, it tests the condition.
     If the condition is true, it fixes `then` (or the date) on this date.
4. **Before a rule reads a solved value,** the executor solves the provisional
   problem again if the state changed since the last solve.
5. **After all rules on the date,** each undecided rule whose window end is now on
   or before the date fixes `otherwise` on this date. A start bound that becomes
   `never` also closes the window.
6. **At the end of the Model timeline,** each undecided rule fixes `otherwise` on
   that date.
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
- **A new stage, decide,** follows it when the Specification has rules. For each
  path, it runs the evaluation order. It calls build problem and solve (stages 4
  and 5) for each provisional solve. It returns the decided values and the trace.
  The stage is the pure function
  `rangekeeper.execution.decide(composition, *, backend, config) -> Decisions`.
- **Stages 4 to 8 then run once** with the decided values fixed. The affine
  problem never contains a rule: a decided value is a fixed value in it.

Rules that read only path Flows, fixed values, parameters and decided values need
no provisional solve. Then each path has one solve. A rule that reads a solved
value adds at most one solve for each decision before it. Worker reuse
([#130](https://github.com/daniel-fink/rangekeeper/issues/130)) keeps this cost
low.

An infeasible provisional solve fails that case. The diagnostic names the review
date, the decided values and the broken constraint (lesson 05, cell 7).

### Simulation, inverse solving and search stay apart

- **Simulation** is this record: a forward solve with rules.
- **Inverse solving.** A Specification with rules can have free inputs only when
  no observation depends on them. Each path then solves its free inputs with its
  final decisions. There is no target over a batch, such as a mean.
- **Policy search** is not in the library. A sweep of rule parameters is a set of
  cases, and cases multiply with paths. [ADR-022](022-design-alternatives.md)
  `best` selects only from the tested cases.

### Decision traces in the Run

The Run report has a `policy_evidence` section. For each case it records:

- **`reviews`:** one record for each review and each `otherwise`. A record has
  the rule key, the date, the kind (review or otherwise), the observations, the
  condition result (true, false or unknown) and the decided value.
- **Observations:** name, reference, quantity, availability date and source (path,
  fixed, parameter, decided or solved).
- **`decided`:** for each key, the value, the decision date and the rule.
- **`verified`:** the result of the trace check, with its diagnostics.

The `Outcome` reads the trace:

- `outcome.decisions()` returns a table with one row for each case and review. It
  has `where(**values)` and `observations()`.
- `outcome.case(key=...).trace()` shows the reviews of one case.
- Decided values appear in `outcome.table(...)` like other values.

The new `Rule`, `Review` and `PolicyEvidence` records replace `Decision`,
`Action` and `DecisionOutcome`. `ObservedQuantity` stays.

### Verification and replay

- **The trace check** is the independent verification of rules
  ([ADR-003](003-computation-and-evidence.md)). It runs after each solve, and on a
  stored Run without a solve. It checks:
  - the dates, the windows, the written order and each observation's availability;
  - that each condition result follows from the recorded observations;
  - that each value is fixed on the first true review, or `otherwise` on the
    correct date;
  - that the candidate contains the decided values;
  - that path observations equal the path data;
  - that solved Flow observations equal the candidate's Movements.
- **Replay.** `rk.execution.replay(run=, store=)` solves again from the pinned
  Specification and MarketPaths. It compares the new trace with the stored trace.
  The decisions and dates must be the same, and the values must agree within
  tolerance. A difference gives the diagnostic `replay_mismatch`, which names the
  first review that differs.

### Paired comparison

`outcome.compare(other=, keys=)` returns a `PairedComparison`:

- Both Outcomes must pin the same `MarketPaths`. If not, `compare` raises
  `ValidationError` with the code `different_market_paths`.
- It pairs cases by path member key. If one Outcome has cases across paths and the
  other has only paths, it pairs each case with the same path in the other.
- It gives the difference for each path and key. It has `summary()` (mean
  difference, share of paths better, worst loss and 5 % quantile), `by(key=)`,
  `by_case()` and `where(**values)`.
- A failed case is not in the differences. `summary()` gives the count of failed
  cases.

### Removed

- `Policy`, `Decision`, the old `Rule`, `Action`, `ActionKind`, `DecisionOutcome`,
  `evaluate` and `observe` leave `specification.policy`.
- The exact Boolean evaluator and the availability rule move into `execution` as
  internal modules.
- The investment resale example uses `decide(key="sale_date", ...)`.

## Worked examples

These come from the proposed cells of lesson 05 (#201). Market values are
illustrative.

**Wait to start (cell 6).**

```python
wait = fixed.decide(key="start_date", when="rent_index >= 1.05", review=yearly,
                    window=(date(2027, 1, 1), date(2031, 1, 1)), otherwise="never")
```

| Date | Kind | Period read | `rent_index` | Condition | Result |
| --- | --- | --- | --- | --- | --- |
| 2027-01-01 | review | 2026 | 1.00 | false | — |
| 2028-01-01 | review | 2027 | 0.97 | false | — |
| 2029-01-01 | review | 2028 | 0.95 | false | — |
| 2030-01-01 | review | 2029 | 1.06 | true | `start_date = 2030-01-01` |

Each review reads the period that ended on the review date. The path must
therefore include the period before the first review. If it does not, the first
review fails with `observation_unavailable`. The rule reads only a path Flow, so
each path has one solve. On this path, B's
fixed start in 2030 is before the shared works finish. The case fails, and the
diagnostic names the constraint `b_start >= shared_start + 1 year` (cell 7). On a
path that never passes 1.05, the 2031-01-01 window end fixes `never`.

**A look-ahead (cell 8).** `when="shift(flow=rent_index, periods=-1) >= 1.05"`
reads the next period. `decide` raises `AvailabilityError` before any solve. The
error has `code`, `value`, `available_on` and `decision_date`.

**Start Building B with a funding check (cell 9).**

```python
start_b = wait.decide(key="b_start", when="rent_index >= 1.10 and funding.headroom >= b_cost",
                      review=yearly, window=("shared_start + 1 year", date(2033, 1, 1)),
                      otherwise="never")
```

The window stays closed until `start_date` is decided. `funding.headroom` is a
solved Flow. On each review, the executor uses the provisional solution with
`start_date` fixed and `b_start` at `never`. After `start_date` is decided, the
first review of B solves again, and later reviews reuse that solution until a
decision changes the state. The headroom on 2031-01-01 is the balance at the end of
the 2030 period.

**Abandon (cell 11).** The rule for `b_sale_date` reads `b_start == never`.
`b_start` is written first. On 2033-01-01, B's rule runs first: its window has
ended, so it fixes `never`. Then the sale rule runs. Its window
`[2033-01-01, 2034-01-01)` is open, and its condition is true. If the sale rule
were written first, `decide` would reject it with `rule_order`.

**A threshold sweep (cell 17).** `parameters(start_threshold=1.05)` and `cases`
make one case for each threshold, across every path. Each case key is a pair of the
case name and the path member key ([ADR-014](014-market-paths.md)).

## Acceptance for #215

1. `decide`, `parameters`, `rules` and `with_rules` return new Specifications. A
   replaced rule keeps its position.
2. `decide` raises `AvailabilityError` for cell 8. It raises `ValidationError`
   with `rule_order` for a reference to a later rule, and with
   `rule_reads_unknown` for an observation that depends on a free input.
3. Unit tests with a fake backend, and no subprocess, cover each step of the
   evaluation order:
   - rules on the same date, and the written order;
   - closing a window when the rule runs, and after the date;
   - undecided window bounds and unknown comparisons;
   - the end of the timeline.
4. A rule set that reads only path values runs one solve for each path. A rule
   set with a funding observation stays within the stated solve bound. The Run
   report records the solve count for each case.
5. A Model with `marketing_start = b_start - 6 months` fails with
   `decision_changes_past`.
6. The trace check passes for each lesson 05 case. Each observation has
   `available_on <= decision_date` (cell 18). A changed trace fails the check.
7. Replay gives the same trace. Replay against changed path data gives
   `replay_mismatch`.
8. `compare` raises `different_market_paths` for different paths. It pairs
   cases across paths, and `summary()` counts failed cases.
9. Lesson 05 cells 5 to 18 run on the three histories and on the CI path count.
   On the three histories, the decisions and equity NPVs agree with an
   independent calculation of the rules on known data.
10. The old policy slice is removed, and the investment example and its tests use
    `decide`. The [scenario reference](../reference/scenarios-and-policies.md) and
    the glossary describe the new terms.

## API names added

- `rk.Specification.decide`, `.parameters`, `.rules` and `.with_rules`.
- `rk.specification.Rule`.
- `rk.execution.decide` and `rk.execution.Decisions` (stage).
- `rk.execution.Outcome.decisions`, `Outcome.compare` and
  `Outcome.case(key=...).trace`.
- `rk.execution.PairedComparison` with `summary`, `by`, `by_case` and `where`.
- `rk.errors.AvailabilityError`.
- Diagnostic codes: `rule_order`, `rule_reads_unknown`,
  `observation_unavailable`, `decision_changes_past`, `replay_mismatch` and
  `different_market_paths`.
- Run records: `PolicyEvidence`, `Review` and `Observation`.

## Alternatives and consequences

- **Evaluate rules once before the solve.** This keeps one solve for each path,
  but a rule cannot read funding. Lesson 05 cell 9 and exercise 2 would change.
- **Solve a truncated problem up to each review date.** Each solve is smaller,
  but every Model would have to be truncatable. NPV, IRR and reversion use the
  whole timeline.
- **One mixed-integer problem with a binary variable for each review.** This is
  optimisation, not simulation, and the backend would not be affine.
- **Let the executor sort rules by their references.** The order would not show in
  the Specification. Lesson 07's design and start rules make a cycle that the
  executor would have to reject.
- **Inclusive windows.** They read like "from 2027 to 2030", but they break the
  half-open time rule of [ADR-012](012-naming-and-glossary.md).
- **Block decisions that the funding cannot cover.** This hides a modelling choice
  in the executor. Lesson 05 shows the commitment gap when the check is missing.
- **Keep the action concept.** Decision D9 of #201 removes it. A rule decides one
  value, and the Model relates the other dates to it.

The rule API replaces the current policy API. This is a breaking change inside the
1.0.0 format reset ([ADR-017](017-api-and-formats.md)). Lesson 05's proposed cells
keep their half-open windows. The rename pass
([ADR-012](012-naming-and-glossary.md)) does not change these names.

## Sources and related decisions

- [ADR-013: execution and extension points](013-execution-and-extensions.md),
  amended by this record for stage 3 and the decide stage.
- [ADR-014: market paths](014-market-paths.md), amended by this record for
  availability and member references (#139).
- [ADR-022: design alternatives](022-design-alternatives.md), which uses these
  rules to choose a design.
- [ADR-020: walkthrough plan v2](020-walkthrough-plan-v2.md), lesson 05.
- Proposed cells for lesson 05 and decisions D2, D8 and D9:
  `examples/walkthrough/proposed/` (#201,
  [#255](https://github.com/daniel-fink/rangekeeper/pull/255)).
- [Scenarios and policies reference](../reference/scenarios-and-policies.md), which
  changes when #215 lands.
- Issues: [#213](https://github.com/daniel-fink/rangekeeper/issues/213) (this
  design), [#215](https://github.com/daniel-fink/rangekeeper/issues/215)
  (implementation), [#139](https://github.com/daniel-fink/rangekeeper/issues/139).

Supersedes: none. Amends: ADR-013, ADR-014. Superseded by: none.
