# Upgrade Rangekeeper

Each section describes one breaking release. Install the library and the examples
from the same reviewed revision. There are no forwarding modules, deprecated
installation extras or automatic schema upgrades.

## Upgrade from 1.0.0a1 to 1.0.0a2

Release 1.0.0a2 moves the modules into the 1.0 layers, applies the glossary names
([ADR-010](../decisions/010-layers-and-packages.md),
[ADR-012](../decisions/012-naming-and-glossary.md)) and resets the document
formats to 1.0.0 ([ADR-017](../decisions/017-api-and-formats.md)). Upgrade in
this order:

1. Run the consumer codemod on your code.
2. Make the changes that the codemod lists but does not make.
3. Rebuild or convert your stored documents and Bundles.
4. Run your tests.

### Run the consumer codemod

The codemod applies the [rename map](#100a2-rename-map) to code that uses
Rangekeeper. It changes imports, qualified names, renamed functions, classes,
attributes and keyword arguments, and Python code blocks in Markdown and
notebooks. It moves no files. The tool is in the Rangekeeper repository, not in
the wheel. The repository includes the index of the 1.0.0a1 package that the tool
needs:

```sh
git clone https://github.com/daniel-fink/rangekeeper.git
cd rangekeeper
git checkout v1.0.0a2
uv sync --only-group codemod --only-group lint
```

Report the changes first. Without `--apply`, the tool writes nothing:

```sh
uv run --no-sync python -m tools.codemod --consumer --index tools/codemod/indexes/rangekeeper-1.0.0a1.json --root ../your-project
```

Then apply them on a branch of your project, and format the changed files:

```sh
uv run --no-sync python -m tools.codemod --consumer --index tools/codemod/indexes/rangekeeper-1.0.0a1.json --root ../your-project --apply --format
```

Add paths after the options to limit the run to some files or folders. A second
run changes nothing. See the [codemod guide](../../tools/codemod/README.md) for
the options and the limits.

### Changes that the codemod does not make

The report lists each use that needs a change by hand. These are the changes:

| 1.0.0a1 | 1.0.0a2 |
| --- | --- |
| `series.align(flows, join=, missing=)` and `Alignment.reduce(...)` | `Stream(flows, join=, missing=).align()`, then `.aggregate(...)` |
| `series.aggregate(flows, ...)` | `Stream(flows).aggregate(...)`, `.sum()`, `.min()` or `.max()` |
| `series.resample(flow, periods=, method=)` | `flow.resample(periods, method=)` returns a Flow; `Stream.resample` also gives coverage |
| `series.multiply(flows)` | `first.multiply(*others)` |
| `series.integrate(flow, ...)` | `flow.integrate(exposures=, day_count=, units=)` |
| `flow.trim(start=, end=)` | `flow.trim(span)` with a Period or Span, as `Stream.trim(span)` |
| `stream.labels` and `select(labels=)` on a value that is not clearly a Stream | `stream.names` and `select(names=)`. Classification `labels` keep their name |
| `from rangekeeper.model.characteristics import Value` (and `Label`, `Characteristics`, `ValueKind`) | `from rangekeeper.model import Value` |
| `characteristics.value(entity.characteristics, key)`, `characteristics.label(...)` | `model.value(owner=entity.id, key=key)`, `model.label(owner=entity.id, key=key)`. A missing key raises `MissingReferenceError` instead of returning `None` |
| Code that reads the wire keys `start_inclusive` and `end_exclusive` | The keys are `start` and `end` |

Each public name has one import path, plus the root re-exports `Model`,
`Specification`, `Run` and `Quantity`. The codemod moves imports of the removed
alias paths, for example `from rangekeeper.model.expression import Reference`
becomes `from rangekeeper.model import Reference`. It lists an access through a
module, such as `system.Entity`, for review.

The codemod does not apply the entries that need later work, for example `pv`,
`npv`, `irr`, growth profiles and the builder names. The map gives their 1.0
names, and the [changes of API shape](#changes-of-api-shape) table lists the
decisions of [#255](https://github.com/daniel-fink/rangekeeper/pull/255) that
change call shapes. A later release makes these changes.

### Document formats 1.0.0

Release 1.0.0a2 resets the Model, Specification and Run formats, and every schema
module, to 1.0.0 ([ADR-017](../decisions/017-api-and-formats.md)). A 1.x reader
reads every format with major version 1, up to its own version. It does not read
0.x documents: Model 0.7.0 and 0.8.0, Specification 0.7.0 and Run 0.4.0 raise
`UnsupportedVersionError`. `rangekeeper.io.migration` and `model_07_to_08` are
removed. Period and Span store `start` and `end`. Model revision identities and
the computation fingerprints change once.

For each stored 0.x document or Bundle, choose one route:

- **Rebuild** it from its source pipeline with 1.0.0a2. Use this route when you
  have the pipeline: it gives documents that the 1.0 code wrote.
- **Convert** it with the one-off [conversion tool](../../tools/upgrade/README.md)
  ([#120](https://github.com/daniel-fink/rangekeeper/issues/120)). Use this route
  for documents that you cannot rebuild, for example a Run with its evidence.

The conversion tool reads Model 0.7.0 and 0.8.0, Specification 0.7.0 and Run
0.4.0, and Bundles that hold them. It changes the format version, the Period and
Span fields `start` and `end`, `policy` to `rules`, `outcomes` to
`rule_evidence`, and currency magnitudes to decimal text. A query `Filter` with a
`classification`, and each Label `Criterion`, gets `exclusive: true`, so it keeps
the exact match of the 0.x formats
([#121](https://github.com/daniel-fink/rangekeeper/issues/121)). Each document
keeps its UUID, so put the converted documents in a new store or Bundle:

```sh
uv run python -m tools.upgrade documents old/model.json old/run.json --output converted
uv run python -m tools.upgrade bundle old-bundle new-bundle
```

Never rewrite the old artifact in place.

#### Currency amounts

From 1.0.0a2, a magnitude in ISO 4217 units, such as `AUD`, is a `Decimal`
([ADR-023](../decisions/023-decimal-money.md)). JSON and YAML store it as
canonical decimal text, `"magnitude": "1250000.5"`, and the JSON reader rejects
a number. The conversion tool rewrites stored documents. In code:

| 1.0.0a1 | 1.0.0a2 |
| --- | --- |
| `quantity.magnitude * 1.1` for a currency Quantity | `quantity.number * 1.1`; a result in currency units becomes an amount when it is a record again |
| `movement.magnitude` in arithmetic | `movement.number` |
| `{"magnitude": 100.0, "units": "AUD"}` in data | `{"magnitude": "100", "units": "AUD"}` |
| `rangekeeper.quantity.minor_unit` | `rangekeeper.money.minor_unit` (the codemod moves it) |
| Rounding by hand | `Quantity.round()`, `money.round()`; the library never rounds on its own |

A scenario realization saved before 1.0.0a2 stays readable as data, but `replay` raises `ReplayUnavailableError` for
it; generate it again.

### Breaking surface for 1.x consumers

This table lists the public names that 1.x consumers use, with their state in
1.0.0a2 and the change that follows before 1.0.0
([#217](https://github.com/daniel-fink/rangekeeper/issues/217)).

| 1.0.0a1 name | 1.0.0a2 | Before 1.0.0 |
| --- | --- | --- |
| `model.system.View` | Unchanged | `View.match(condition=)` and `View.where(condition=)` take a declarative `rangekeeper.model.Filter` ([#121](https://github.com/daniel-fink/rangekeeper/issues/121)) |
| `model.system.Hierarchy` | Unchanged | — |
| `model.system.Reduction`, with `execute`, `pivot`, `Contributor` and callable contributors | Unchanged | `QuantityRollup(key=, units=, reducer=)` and `FlowRollup(key=, reducer=, ...)` with one `Reducer` enum; both default to leaf contributors; `View.aggregate` becomes `View.rollup(definition=)` ([#158](https://github.com/daniel-fink/rangekeeper/issues/158)) |
| `model.system.reduction.Aggregation` | `RollupResult` (the codemod renames it) | — |
| `calculations.series.Aggregation` | `rangekeeper.flow.FlowAggregate` (the codemod renames it) | — |
| `model.system.reduction.AggregateEntry`, `Coverage`, `CoverageStatus` | Unchanged | `rangekeeper.model.system.rollup.RollupEntry`, `Coverage`, `CoverageStatus` ([#158](https://github.com/daniel-fink/rangekeeper/issues/158)); `Coverage.undecided` lists the owners that a `Filter` contributor rule could not decide; missing values never count as zero, and `FlowRollup` refuses `MissingValueHandling.ZERO` ([#157](https://github.com/daniel-fink/rangekeeper/issues/157)) |
| `model.system.Pivot`, `PivotColumn`, `Partition` | Unchanged | `pivot(..., label=)` splits the columns by a label key; `PivotColumn.aggregation` becomes `result` ([#158](https://github.com/daniel-fink/rangekeeper/issues/158), [#159](https://github.com/daniel-fink/rangekeeper/issues/159)) |
| `model.system.classified`, `Model.descendants` | Unchanged | — |
| `model.system.reducers` | Unchanged | Removed: the `Reducer` enum replaces it ([#158](https://github.com/daniel-fink/rangekeeper/issues/158)) |
| `shared.units.UnitSystem`, `default_units` | `rangekeeper.quantity.UnitSystem`, `default_units` (the codemod moves them). `Model.unit_system` is unchanged | — |
| `model.measure.Quantity`, `model.Quantity` | `rangekeeper.Quantity` and `rangekeeper.quantity.Quantity` (the codemod moves them) | Quantity text in API arguments ([#255](https://github.com/daniel-fink/rangekeeper/pull/255) D13, D16) |
| `model.system.System`, `Entity`, `Assembly`, `Relationship` | `rangekeeper.model` only (the codemod moves them). `model.system` keeps the views, rollups and pivots | — |
| `model.characteristics.value`, `label` | Removed. `Model.value(owner=, key=)` and `Model.label(owner=, key=)` raise `MissingReferenceError` for a missing key | — |
| `rangekeeper.Model`, `model.Definitions` | Unchanged; the Model format is 1.0.0 | Builder names ([#255](https://github.com/daniel-fink/rangekeeper/pull/255) D6, D16) |
| `io.bundle.Reader`, `write`, `Reader(..., check_index=False)` | Unchanged API. A Bundle with 0.x documents does not open | Identifiers `rangekeeper.bundle/1` and `rangekeeper.parquet/1`; the format freezes at 1.0.0b1 (ADR-017) |

Three routes help a 1.x consumer:

- the consumer codemod, above;
- deterministic builds with a namespace, as a tested contract
  ([#147](https://github.com/daniel-fink/rangekeeper/issues/147)), so that a
  rebuild from source pipelines gives the same identities each time;
- rebuild or convert for stored Bundles
  ([#120](https://github.com/daniel-fink/rangekeeper/issues/120)).

## 1.0.0a2 rename map

Release 1.0.0a2 moves modules into the 1.0 layers and applies the glossary names
([ADR-010](../decisions/010-layers-and-packages.md),
[ADR-012](../decisions/012-naming-and-glossary.md)). The
[codemod](../../tools/codemod/README.md) applies this map. The map file
[`tools/codemod/rename_map.yaml`](../../tools/codemod/rename_map.yaml) is the source
of these tables.

Each entry has a status:

- **agreed**: an accepted ADR gives the 1.0 name.
- **draft**: the ADR or a walkthrough decision of
  [#255](https://github.com/daniel-fink/rangekeeper/pull/255) gives the direction,
  and the map gives the exact name
  ([#93](https://github.com/daniel-fink/rangekeeper/issues/93)).
- **open**: the 1.0 name is not decided. The codemod does not apply it.

"Needs schema" means that the name is a generated record field; the schema changes
first. "Needs refactor" means that the change is more than a rename or a move.

<!-- rename-map:start (generated by tools/codemod/render.py) -->

### Module moves

| Current | 1.0 | Status | Notes |
| --- | --- | --- | --- |
| `rangekeeper.model.duration` | `rangekeeper.duration` | agreed |  |
| `rangekeeper.model.flux` | `rangekeeper.flow` | draft | Stream and the Flow re-exports become the `flow` package module. |
| `rangekeeper.model._flow_mapping` | `rangekeeper.flow._mapping` | draft |  |
| `rangekeeper.calculations._batch` | `rangekeeper.flow._batch` | draft | The private calculation engine. |
| `rangekeeper.calculations.series` | `rangekeeper.flow` | agreed | The module is removed (#103). Its options and FlowAggregate are in `rangekeeper.flow`; Flow and Stream methods replace its functions (see the removed names). |
| `rangekeeper.schema.behaviors.flow` | `rangekeeper.flow` | agreed | The behaviour modules are removed; generated records contain data only. Flow, Movement and MissingValueHandling are in `rangekeeper.flow`. Period and Span are in `rangekeeper.duration`; Distribution stays in `rangekeeper.model`. |
| `rangekeeper.calculations` | `rangekeeper.finance` | agreed |  |
| `rangekeeper.calculations.projection` | `rangekeeper.profile` | agreed | Growth and distribution profiles. The word "projection" is not used. Profile classes and `Flow.from_profile` follow (#303). |
| `rangekeeper.calculations.dynamics` | `rangekeeper.market.dynamics` | agreed | Path generators are series maths, so they leave `finance`. `rk.market.Dynamics` follows (#299). |
| `rangekeeper.run.execution` | `rangekeeper.execution` | agreed |  |
| `rangekeeper.specification.policy` | `rangekeeper.specification.rule` | agreed | "Policy" is not used. The rule queries of ADR-021 replace the records later (#215). |
| `rangekeeper.specification.policy.evaluation` | `rangekeeper.execution.rule.evaluation` | agreed | Rule evaluation moves to `execution`. `specification.rule` keeps the declarations. Import `evaluate` from `rangekeeper.execution.rule`. |
| `rangekeeper.specification.policy.observation` | `rangekeeper.execution.rule.observation` | agreed |  |
| `rangekeeper.specification.policy.result` | `rangekeeper.execution.rule.result` | agreed |  |
| `rangekeeper.specification.policy.predicate` | `rangekeeper.run._rule.predicate` | draft | Internal. The exact Boolean truth of a condition is shared by the evaluator and the trace check of a stored Run, so it is below `execution`. |
| `rangekeeper.specification.policy._availability` | `rangekeeper.run._rule.availability` | draft | Internal. Shared by the evaluator and the trace check of a stored Run. |
| `rangekeeper.shared.units` | `rangekeeper.quantity` | agreed | The namespace that holds the unit system, the registry and `isclose` is `rangekeeper.quantity`, so "units" keeps one meaning: a unit string. `Quantity` is also at the root. |
| `rangekeeper.io.store` | `rangekeeper.io` | agreed | The `RecordStore` protocol is defined in the internal `shared.store`, so `execution` does not import `io`. Import `RecordStore` and `Document` from `rangekeeper.io`. |
| `rangekeeper.model.system.projection` | `rangekeeper.model.system.table` | draft |  |
| `rangekeeper.model.scenario` | `rangekeeper.market` | agreed | The generators, paths and replay move as they are. `rk.market.Paths` and the MarketPaths document replace the scenario plan (#298, #299). |
| `rangekeeper.model.scenario.market` | `rangekeeper.market.generation` | draft | Sampling, capture and realization of market paths; `rangekeeper.market.market` would repeat the name. |
| `rangekeeper.model.system.reduction` | `rangekeeper.model.system.rollup` | agreed | `QuantityRollup` and `FlowRollup` replace `Reduction`; see the symbol entries. |
| `rangekeeper.model.scope` | `rangekeeper.model._scope` | agreed | Internal. The checks over raw mappings become private; the typed target lookups move to `rangekeeper.model.targets`. |
| `src/tests/` | `tests/` | agreed | The pass moves the suite to the top level. #177 adds the sub-folders that mirror the packages, and tests/contracts, tests/integration and tests/walkthrough. |

### Renamed names

| Current | 1.0 | Status | Notes |
| --- | --- | --- | --- |
| `rangekeeper.calculations.series.Aggregation` | `FlowAggregate` | draft |  |
| `rangekeeper.model.system.reduction.Aggregation` | `RollupResult` | draft |  |
| `rangekeeper.model.system.reduction.Reduction` | `rangekeeper.model.system.rollup.QuantityRollup` | agreed (needs refactor) | The scalar and Flow modes split. `Reduction(select=select_value(key), reducer=reducers.sum, units=)` becomes `QuantityRollup(key=, units=, reducer=Reducer.SUM)`; `Reduction.flows(key=, aggregation=, ...)` becomes `FlowRollup(key=, reducer=, ...)`. Both default to `Contributor.LEAVES`; the scalar default was every node. Custom selectors and reducers are removed. |
| `rangekeeper.model.system.reduction.AggregateEntry` | `rangekeeper.model.system.rollup.RollupEntry` | agreed | `aggregate` is the word for combining Flows (D38). |
| `rangekeeper.model.duration.calendar.measure` | `count_steps` | draft |  |
| `rangekeeper.model.duration.period.align` | `containing_period` | draft |  |
| `rangekeeper.model.measure.Quantity` | `rangekeeper.quantity.Quantity` | agreed | `rangekeeper.Quantity` at the root also gives the record. |
| `rangekeeper.model.measure.Measure` | `rangekeeper.model.Measure` | draft | The `model.measure` shim is removed; `rangekeeper.model` re-exports the record. |
| `rangekeeper.model.distribution.Distribution` | `rangekeeper.model.Distribution` | draft | The `model.distribution` shim is removed. |
| `rangekeeper.model.distribution.DistributionFamily` | `rangekeeper.model.DistributionFamily` | draft |  |
| `rangekeeper.model.system.System` | `rangekeeper.model.System` | agreed | One canonical path for each public name. |
| `rangekeeper.model.system.Entity` | `rangekeeper.model.Entity` | agreed | One canonical path for each public name. |
| `rangekeeper.model.system.Assembly` | `rangekeeper.model.Assembly` | agreed | One canonical path for each public name. |
| `rangekeeper.model.system.Relationship` | `rangekeeper.model.Relationship` | agreed | One canonical path for each public name. |
| `rangekeeper.model.expression.Expression` | `rangekeeper.model.Expression` | agreed | One canonical path for each public name. |
| `rangekeeper.model.expression.Reference` | `rangekeeper.model.Reference` | agreed | One canonical path for each public name. |
| `rangekeeper.model.expression.Function` | `rangekeeper.model.Function` | agreed | One canonical path for each public name. |
| `rangekeeper.model.expression.Domain` | `rangekeeper.model.Domain` | agreed | One canonical path for each public name. |
| `rangekeeper.model.expression.Constraint` | `rangekeeper.model.Constraint` | agreed | One canonical path for each public name. |
| `rangekeeper.model.formulation.Formulation` | `rangekeeper.model.Formulation` | agreed | One canonical path for each public name. |
| `rangekeeper.model.formulation.Binding` | `rangekeeper.model.Binding` | agreed | One canonical path for each public name. |
| `rangekeeper.model.scenario.Binding` | `rangekeeper.model.Binding` | agreed | One canonical path for each public name. |
| `rangekeeper.model.scenario.Distribution` | `rangekeeper.model.Distribution` | agreed | One canonical path for each public name. |
| `rangekeeper.model.Quantity` | `rangekeeper.quantity.Quantity` | agreed | One canonical path for each public name. |
| `rangekeeper.schema.behaviors.flow.MissingValueHandling` | — | open | One persisted enum (MissingHandling) and one runtime enum with a distinct name. |
| `rangekeeper.calculations.financial.calculate_pv` | `pv` | agreed (needs refactor) | `rangekeeper.finance.pv(flow=, rate=, on=)`, with keyword-only arguments (#167). |
| `rangekeeper.calculations.financial.calculate_xnpv` | `npv` | agreed (needs refactor) | `rangekeeper.finance.npv(flow=, rate=, on=)`, with keyword-only arguments (#167). |
| `rangekeeper.calculations.financial.calculate_irr` | `irr` | agreed (needs refactor) | `rangekeeper.finance.irr(flow=)`, also an equation function (#164, #167). |
| `rangekeeper.calculations.projection.ProjectionMethod` | `GrowthMethod` | draft | The word "projection" is not used. Profile classes replace the enum (#303). |
| `rangekeeper.calculations.projection.project_values` | `grow_values` | draft | The word "projection" is not used. `Flow.from_profile` replaces it (#303). |
| `rangekeeper.model.formulation.account.interest` | `rangekeeper.model.formulation.financial.interest` | draft | The account module is removed; passive interest stays with the other financial equations. |
| `rangekeeper.model.scenario.replay.replay` | `rangekeeper.market.replay` | agreed | One canonical path for each public name. |
| `rangekeeper.model.scenario.replay.ReplayUnavailableError` | `rangekeeper.market.ReplayUnavailableError` | agreed | One canonical path for each public name. |
| `rangekeeper.schema.records.Policy` | `RuleSet` | draft (needs schema) | The record that a Specification holds as `rules`. The schema module `policy` becomes `rule`. `Rule` keeps its name. ADR-021's rule queries replace these records (#215). |
| `rangekeeper.schema.records.DecisionOutcome` | `RuleEvidence` | draft (needs schema) | The evidence of one rule decision, in `Report.rule_evidence`. |
| `rangekeeper.specification.policy.result.PolicyResult` | `RuleResult` | agreed |  |
| `rangekeeper.specification.policy.observation.PolicyCapabilityError` | `RuleCapabilityError` | agreed |  |
| `rangekeeper.specification.policy.validation.validate_policy` | `validate_rules` | agreed |  |
| `rangekeeper.specification.policy.validation.validate_outcomes` | `rangekeeper.run._rule.evidence.validate_evidence` | agreed | The trace check of the `RuleEvidence` records of a Run report. It is evidence validation, so it moves to the internal `run._rule` (#102). |
| `rangekeeper.specification.policy.evaluate` | `rangekeeper.execution.rule.evaluate` | agreed | `specification.rule` exports only the declarations. |
| `rangekeeper.specification.policy.observe` | `rangekeeper.execution.rule.observe` | agreed |  |
| `rangekeeper.specification.policy.Observation` | `rangekeeper.execution.rule.Observation` | agreed |  |
| `rangekeeper.specification.policy.PolicyResult` | `rangekeeper.execution.rule.RuleResult` | agreed |  |
| `rangekeeper.specification.policy.PolicyCapabilityError` | `rangekeeper.execution.rule.RuleCapabilityError` | agreed |  |
| `rangekeeper.execution.errors.UnsupportedProblem` | `UnsupportedError` | agreed | Every error name ends in `Error`. |
| `rangekeeper.model.expression.evaluation.UnsupportedExpression` | `UnsupportedError` | agreed | One error for unsupported expressions and problems. |
| `rangekeeper.execution.errors.BackendUnavailable` | `BackendUnavailableError` | agreed |  |
| `rangekeeper.execution.errors.AttemptDeadline` | `AttemptDeadlineError` | agreed |  |
| `rangekeeper.execution.backends.base.Result` | `rangekeeper.execution.backends.BackendResult` | agreed | `termination` is a `Termination`, not a backend word; the backend's own condition moves into `evidence`. A backend also returns its `limits` and `diagnostics`. |
| `rangekeeper.execution.compiler.Compiled` | `rangekeeper.execution.AffineProblem` | agreed | The typed result of the build-problem stage. |
| `rangekeeper.execution.compiler.compile` | `rangekeeper.execution.build_problem` | agreed | `build_problem(binding, limits=)` also checks the symbol and constraint limits; `constraint_limit=` is replaced by `limits=`. |
| `rangekeeper.execution.preparation.Prepared` | `rangekeeper.execution.Binding` | agreed | The typed result of the bind-roles stage. |
| `rangekeeper.execution.publication.candidate` | `rangekeeper.execution.make_candidate` | agreed |  |
| `rangekeeper.execution.acceptance.check` | `rangekeeper.execution.verify` | agreed |  |
| `rangekeeper.execution.acceptance.Acceptance` | `rangekeeper.execution.Verification` | agreed |  |
| `rangekeeper.model.scope.target_value` | `rangekeeper.model.targets.target_value` | agreed |  |
| `rangekeeper.model.scope.target_units` | `rangekeeper.model.targets.target_units` | agreed |  |
| `rangekeeper.model.scope.recorded_scalar` | `rangekeeper.model.targets.recorded_scalar` | agreed |  |
| `rangekeeper.quantity.minor_unit` | `rangekeeper.money.minor_unit` | agreed | The money module owns the ISO 4217 catalogue, boundaries and rounding. |
| `rangekeeper.flow.ResamplingMethod` | `ResampleMethod` | agreed | The enum also gains SPLIT, which divides each amount over shorter Periods. |
| `rangekeeper.model.expression.Criterion` | `rangekeeper.model.Criterion` | agreed | `rangekeeper.model` exports the query Filter with its Criterion and ValueTest records. |
| `rangekeeper.model.expression.Direction` | `rangekeeper.model.Direction` | agreed | A fixed word that rangekeeper defines is an enum with one public path. |
| `rangekeeper.run.Status` | `RunStatus` | agreed | The record at `run.report.status`, with `completion` and `solution`. `rk.execution.Status` is the Status of an Outcome, a different type. |
| `rangekeeper.schema.records.Status` | `RunStatus` | agreed (needs schema) | The generated record; the LinkML class is `RunStatus`. Stored Runs do not change. |
| `rangekeeper.execution.compiler.Compiled.prepared` | `binding` | agreed |  |
| `rangekeeper.model.system.view.View.aggregate` | `rollup` | agreed | Each use needs review. `view.aggregate(reduction)` becomes `view.rollup(definition=rollup)`. |
| `rangekeeper.model.system.pivot.PivotColumn.aggregation` | `result` | agreed | Each use needs review. |
| `rangekeeper.specification.specification.Specification.lock` | `fix` | agreed |  |
| `rangekeeper.specification.specification.Specification.unlock` | `free` | agreed |  |
| `rangekeeper.schema.records.Period.start_inclusive` | `start` | agreed | Also Span. Half-open; the end is excluded. The package pass changed the schema in 1.0.0a2 (#119), so the consumer pass applies this entry. |
| `rangekeeper.schema.records.Period.end_exclusive` | `end` | agreed | Also Span. |
| `rangekeeper.model.flux.Stream.labels` | `names` | draft | Each use needs review. Classification `labels` keep their name. The package pass renamed the Stream field by hand; the consumer pass lists the uses to check. |
| `rangekeeper.schema.records.Specification.policy` | `rules` | draft (needs schema) | Each use needs review. The Specification field and its wire key. `spec.rules` holds all of a Specification's rules. |
| `rangekeeper.schema.records.Report.outcomes` | `rule_evidence` | draft (needs schema) | Each use needs review. The Run report field and its wire key. |
| `rangekeeper.specification.policy.result.PolicyResult.outcomes` | `evidence` | agreed | Each use needs review. The `RuleEvidence` records of one evaluation. |
| `findings` | `diagnostics` | draft | Each use needs review. |
| `issues` | `diagnostics` | draft | Each use needs review. |
| Any call: `start_inclusive=` | `start=` | agreed |  |
| Any call: `end_exclusive=` | `end=` | agreed |  |
| `rangekeeper.specification.policy.evaluation.evaluate`: `policy=` | `rules=` | agreed |  |
| `rangekeeper.model.flux.Stream.select`: `labels=` | `names=` | draft |  |
| `rangekeeper.model.flux.Stream.from_values`: `labels=` | `names=` | draft |  |

### Removed names

| Current | Use instead | Status |
| --- | --- | --- |
| `rangekeeper.duration.Frequency.BIWEEK` | `offset(..., frequency=Frequency.WEEK, count=2)` for a 14-day step, or explicit 14-day Periods for a grid. There is no fortnight frequency | agreed |
| `rangekeeper.model.system.reducers` | The `rangekeeper.model.system.Reducer` enum: `SUM`, `MEAN`, `MIN`, `MAX` and `COUNT`, passed as `reducer=` to `QuantityRollup` or `FlowRollup` | agreed |
| `rangekeeper.calculations.account` | Compose the funding with Flows: a balance is `cumulative()`. Interest is the Model equation `rangekeeper.model.formulation.financial.interest`; `rx.finance.interest` in equation text follows (#255 D2, D23, #278). A how-to recipe follows (#194) | agreed |
| `rangekeeper.model.formulation.account.schedule` | Equations over Flows, such as `funding_need = -(net_cash_flow + loan_interest).cumulative()`. A Model declares no account (#255 D2) | agreed |
| `rangekeeper.model.expression.authoring.sum` | Equation text or `rangekeeper.expressions` on entity handles (#255 D6, D18, D32). ADR-012 forbids public names that shadow builtins | agreed (needs refactor) |
| `rangekeeper.model.formulation.authoring.declare` | `rk.Model(name=)`, `model.edit()` and entity handles with `value(key=, units=)`, `flow(...)`, `date(...)` and `equations(...)` (#255 D6, D16) | agreed (needs refactor) |
| `rangekeeper.calculations.series.align` | Stream(flows, join=, missing=).align() | agreed |
| `rangekeeper.calculations.series.multiply` | Flow.multiply(*others) | agreed |
| `rangekeeper.calculations.series.integrate` | Flow.integrate(exposures=, day_count=, units=) | agreed |
| `rangekeeper.calculations.series.resample` | Flow.resample(periods, method=) and Stream.resample(periods, method=) | agreed |
| `rangekeeper.calculations.series.aggregate` | Stream.aggregate(method=), Stream.sum(), Stream.min() and Stream.max() | agreed |
| `rangekeeper.calculations.series.Alignment` | The Stream that Stream.align() returns; Stream.aggregate() replaces Alignment.reduce() | agreed |
| `rangekeeper.model.characteristics` | `Model.value(owner=, key=)` and `Model.label(owner=, key=)`; the records are re-exported in rangekeeper.model | agreed |
| `rangekeeper.model.characteristics.value` | `model.value(owner=entity.id, key=)`. A missing key raises MissingReferenceError instead of returning None | agreed |
| `rangekeeper.model.characteristics.label` | `model.label(owner=entity.id, key=)`. A missing key raises MissingReferenceError instead of returning None | agreed |
| `rangekeeper.model.scenario.market.ScenarioPlan` | Path generators and the MarketPaths document | agreed (needs refactor) |
| `rangekeeper.model.scenario.market.sample` | Path generators and the MarketPaths document | agreed (needs refactor) |
| `rangekeeper.model.scenario.market.capture` | Path generators and the MarketPaths document | agreed (needs refactor) |
| `rangekeeper.model.scenario.market.realize` | Path generators and the MarketPaths document | agreed (needs refactor) |
| `rangekeeper.model.scenario.market.generate` | Path generators and the MarketPaths document | agreed (needs refactor) |
| `rangekeeper.model.scenario.view.Market` | The MarketPaths document | agreed (needs refactor) |
| `rangekeeper.execution.compiler.Row.scale` | Rows are unscaled. `PyomoHighs.scale(row)` gives the divisor of the `pyomo-highs` backend | agreed |
| `rangekeeper.execution.executor.Executor` | `rangekeeper.execution.execute(specification, store, config=)`, which returns an `Outcome`; read the Run as `outcome.run`. Use `rangekeeper.execution.solve(specification, config=)` to write nothing | agreed |
| `rangekeeper.execution.publication.CandidateResolver` | `rangekeeper.execution.assembly.Overlay(resolver, models=, runs=)` | agreed |
| `rangekeeper.execution.planning.Plan` | `rangekeeper.execution.resolve_cases(specification, resolver=)`. It returns `Cases`, which is also a resolver | agreed |
| `rangekeeper.execution.preparation.prepare` | `rangekeeper.execution.validate(composition, resolver=, units=)`, then `rangekeeper.execution.bind_roles(validation)` | agreed |
| `rangekeeper.shared.errors.BoundaryError` | rangekeeper.errors.RangekeeperError | agreed |
| `rangekeeper.shared.errors.ValueEncodingError` | rangekeeper.errors.EncodingError | agreed |

### Changes of API shape

These decisions change API shapes, not only names. The codemod does not apply
them; the issues that the table names make the changes.

| Topic | 1.0 | Source |
| --- | --- | --- |
| Quantity text in API arguments | Arguments take unit text such as `"7 % pa"`; `per` divides and `pa` means per year. | #255 D13, D16, D17 |
| Execution configuration | `Executor(store, backend=, units=, tolerances=)` becomes `execute(specification, store, config=ExecutionConfig(backend=, units=, tolerances=))`. `ExecutionConfig` also holds the default `limits` and the `backend_options`. | ADR-013, #128 |
| Keyword-only arguments | Every Rangekeeper call names its arguments. | #255 D14 |
| Model authoring and builder names | `rk.Model(name=)`, `model.edit()`, `ModelDraft.add_entity(code=)` and entity handles. `Model(record, units=)` is removed: `rk.Model(name=)` makes an empty Model, and `Model.create(...)` or `Model.from_data(...)` take complete records (#141, #281). | #255 D6, D16, D18 |
| Specification calls | `fix`, `free`, `cases`, `across` and `parameters` each return a new Specification; unfixed values are free. `model.specify(name=)` makes one. `fix(target, quantity, id=, model=, ids=, recorded=)` is now `fix(key=quantity)`, or `fix({target: quantity})` for a dotted path, a UUID or a mapping of Movement UUIDs; `free(target, id=, model=, ids=)` is now `free(*targets)`. The Specification keeps its Model: pass `Specification(record, model=, resolver=)` for a record. `recorded=True` is removed: fix the recorded Quantities explicitly (#144). `fix` also takes Quantity text and a number for a ratio; a number for a value with other units raises `UnitError`, not `TypeError`. `specify` and each call record as unknowns the values that the equations use and that nothing fixes, so `free` is needed only to release a fixed value. `roles` lists the role of each value as an `rk.specification.Role` (#290). | #255 D7, D8 |
| Loan payment | `rangekeeper.finance.payment(principal=, rate=, term=, frequency=)` (#167). | #255 D19 |
| Funding accounts | There is no account class and no account declaration. A balance is `cumulative()` of a Flow. | #255 D2, D23 |
| Growth and distribution profiles | `rk.profile.Constant`, `Linear`, `Compounding`, `Uniform` and `SCurve` with `rk.flow.Flow.from_profile(profile=, periods=, initial= or total=)` replace `extrapolate`, `distribute` and `GrowthMethod` (#303). | #255 D12 |
| Market paths | `rk.market.Dynamics`, `rk.market.generate` and `rk.market.Paths` replace the scenario plan and the trend and cycle kernels (#298, #299). | #255 D29, D31 |
| Fixed words are enums | Diagnostic codes are `rk.errors.Code` (#154); "the event does not happen" is `rk.duration.NEVER`; `Role`, `DecisionResult`, `Status` and `Direction` are enums. Words that the data defines stay strings. | #255 D26 |
| Rules | A rule is a query, `rk.specification.Window(...).where(condition=).first(otherwise=)`, fixed by key. The `Rule`, `Check` and `RuleEvidence` records of ADR-021 replace `RuleSet`, `Decision` and `Action` (#215). | ADR-021, #255 D41, D42 |

<!-- rename-map:end -->

## Upgrade from 0.8 to 1.0.0a1

There was no 0.9 release. This is a breaking library change.

| Previous import | Current owner and import |
| --- | --- |
| `rangekeeper.adapters.plotting` | Walkthrough helper `helpers.chart` |
| `rangekeeper.adapters.presentation` | RK `Stream.display()` and `Pivot.display()`, in `rangekeeper.model.display` |
| `rangekeeper.adapters.visualization.graph_html` | Walkthrough helper `helpers.graph.graph_html` |
| `rangekeeper.adapters.visualization` hierarchy charts | Walkthrough helper `helpers.chart` |
| `rangekeeper.adapters.polars` | RK `rangekeeper.io.polars` |
| Canonical Speckle envelope codec | Walkthrough helper `helpers.speckle` |
| `rangekeeper.visualisation.*` and the `visualisation` extra (1.0) | Walkthrough helpers in [`examples/walkthrough/helpers`](../../examples/walkthrough/README.md); table display is `Stream.display()` |

Source readers, workflow orchestration, transient extraction objects and advanced
application browsing are no longer RK APIs. Consumers must supply those features
separately and create canonical records through the public library API.

Use the [walkthrough environment](walkthroughs.md#explore-the-lessons) for the walkthroughs.
For scalar CSV output, call `rangekeeper.io.polars.text_frame(table).write_csv(path)`.
Supply read dtypes explicitly. CSV does not preserve a complete canonical Model.

The old Python and C# runtimes, the `migration` package and the draft schema
upgraders are removed. From 1.0.0a2, 1.x does not read 0.x Model, Specification
and Run documents, because the formats reset to 1.0.0. Rebuild them, or convert
them with `python -m tools.upgrade`; see
[document formats 1.0.0](#document-formats-100). Retained historical source
formats require explicit conversion supplied by the consumer. Historical evidence
and source files remain in the repository. They do not restore removed APIs.

Generic Grasshopper authoring stays in RK. Source-specific extraction belongs to
the consumer. See the [Grasshopper example](../../examples/grasshopper/README.md).

### Classification filters include sub-types

`View.filter(entity_classification=id)` and `relationship_classification=id` now
include the Classification's sub-types. Pass `exclusive=True` to keep the earlier
exact match. `Model.find_entities(classification=id)` still matches exactly. See
[ADR-009](../decisions/009-classification-sub-types.md).

### Geometry and Bundle IO

The [Bundle reference](../reference/bundle.md) defines the optional IO and the
Model Geometry field.
