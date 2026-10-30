# Upgrade Rangekeeper

Each section describes one breaking release. Install the library and the examples
from the same reviewed revision. There are no forwarding modules, deprecated
installation extras or automatic schema upgrades.

## Upgrade from 1.0.0a2 to 1.0.0b1

Release 1.0.0b1 freezes the public API and the stored formats
([ADR-017](../decisions/017-api-and-formats.md)). This section lists the
changes on `develop` that need an action.

### Stored query Filters

1.0.0a2 writes format 1.0.0, and 1.0.0b1 reads it, but one meaning changes
([#121](https://github.com/daniel-fink/rangekeeper/issues/121),
[#386](https://github.com/daniel-fink/rangekeeper/issues/386)). In 1.0.0a2, the
`classification` of a query `Filter` and each Label `Criterion` match exactly.
From 1.0.0b1 they also match sub-types in the Taxonomy, unless `exclusive` is
true. So a stored 1.0.0a2 Filter selects more Entities when 1.0.0b1 reads it.
Also, a Bundle that 1.0.0a2 wrote does not open in 1.0.0b1: its schema pin is
the 1.0.0a2 slot map.

Convert the documents and Bundles that 1.0.0a2 wrote, or rebuild them with
1.0.0b1. The [conversion tool](../../tools/upgrade/README.md) adds
`exclusive: true` to each Filter that has a `classification` and to each
Criterion, so that they keep the 1.0.0a2 meaning. Nothing else changes:

```sh
uv run python -m tools.upgrade documents --from 1.0.0a2 old/model.json --output converted
uv run python -m tools.upgrade bundle --from 1.0.0a2 old-bundle new-bundle
```

A 1.0.0 document does not record the release that wrote it, so convert only the
documents that 1.0.0a2 wrote. The tool refuses a document that already has
`exclusive`. Each document keeps its UUID, so put the converted documents in a
new store or Bundle.

`exclusive` is `true` or absent: absent means that sub-types match. Validation
refuses `exclusive: false`, `exclusive: null` and a Filter with `exclusive` but
no `classification`. In code, omit `exclusive` instead of passing `False`.

### Keyword-only arguments

Public functions and records take their arguments by name (D14,
[#410](https://github.com/daniel-fink/rangekeeper/issues/410)). A call that
passes them by position raises `TypeError`. A call with more than one argument
names all of them, also its first argument. The exceptions are a function with
one argument in all, a natural pair such as `start, end`, a list of any length,
the store-protocol methods, the Python protocol methods, an error constructor
(the message first) and one positional-only mapping
(`Specification.fix(targets, /, **values)`). Name the arguments:

| Layer | 1.0.0a2 | 1.0.0b1 |
| --- | --- | --- |
| `flow` | `Flow.from_periods(periods, magnitudes, units=)` | `Flow.from_periods(periods=, magnitudes=, units=)` |
| `flow` | `Flow.from_events(dates, magnitudes, units=)` | `Flow.from_events(dates=, magnitudes=, units=)` |
| `flow` | `Stream.from_values(model, value_ids)` | `Stream.from_values(model=, value_ids=)` |
| `flow` | `FlowAggregate(flow, coverage)`, `StreamTable(stream)` | `FlowAggregate(flow=, coverage=)`, `StreamTable(stream=)` |
| `profile` | `SCurve(distribution)` | `SCurve(distribution=)` |
| `finance` | `financial.calculate_pv(flow, rate=)`, and the same for `calculate_xnpv` and `calculate_irr` | `financial.calculate_pv(flow=, rate=)`, `calculate_xnpv(flow=, ...)`, `calculate_irr(flow=)` |
| `finance` | `IrrResult(rate, residual, guess)` | `IrrResult(rate=, residual=, guess=)` |
| `market` | `dynamics.calculate_autoregression(innovations, parameter=)`, `accumulate_volatility(trend, returns, ...)`, `calculate_shock(events, ...)` | `calculate_autoregression(innovations=, parameter=)`, `accumulate_volatility(trend=, returns=, ...)`, `calculate_shock(events=, ...)` |
| `model` | `pivot.value(row, column)`, and the same for `available_value`, `cell`, `coverage` and `partition` | `pivot.value(row=, column=)`; `column` stays optional |
| `model` | `Pivot(rows, columns, label=)` | `Pivot(rows=, columns=, label=)` |
| `model` | `system.classified(model, classification, exclusive=)` | `classified(model=, classification=, exclusive=)` |
| `model` | `system.membership.entities_in(model, assembly)`, `relationships_in(model, assembly)`, `containing_assemblies(model, entity)` | `entities_in(model=, assembly=)`, `relationships_in(model=, assembly=)`, `containing_assemblies(model=, entity=)` |
| `model` | `formulation.declare(id, name, equations, values)` | `declare(id=, name=, equations=, values=)` |
| `model` | `formulation.flow.shape(model, value)`, `aligned(model, members, reference)` | `shape(model=, value=)`, `aligned(model=, members=, reference=)` |
| `model` | `Coverage`, `RollupEntry`, `RollupResult`, `Match`, `PivotColumn`, `Partition`, and the table columns `FieldColumn`, `ValueColumn`, `LabelColumn`, `PropertyColumn` | The same records, by keyword: `ValueColumn(name="net_area", key="net", units="meter**2")` |
| `model` | `model.entity(id)`, `model.value(id)`, `model.label(id)`, `draft.entity(id)` | `model.entity(id=)`, `model.value(id=)`, `model.label(id=)`, `draft.entity(id=)`; `code=`, `name=`, `owner=` and `key=` do not change |
| `model` | `Model.from_data(data, units=)` | `Model.from_data(data=, units=)` |
| `model` | `system.View(model, assembly=)`, `view.quantities(key, units=)` | `View(model=, assembly=)`, `view.quantities(key=, units=)` |
| `model` | `Hierarchy(view, membership_root=)`, `Hierarchy.from_membership(view, root=)` | `Hierarchy(view=, membership_root=)`, `Hierarchy.from_membership(view=, root=)` |
| `model` | `rollup.pivot(hierarchy, by=)`, `flow_rollup.formulate(hierarchy, id=, aggregates=)` | `pivot(hierarchy=, by=)`, `formulate(hierarchy=, id=, aggregates=)` |
| `model` | `system.selection.select_value(key, measure=)`, `system.table.to_table(source, columns=)`, `system.matching.match(model, entities, condition)` | `select_value(key=, measure=)`, `to_table(source=, columns=)`, `match(model=, entities=, condition=)` |
| `model` | The `formulation.financial`, `flow` and `growth` builders and `formulation.hierarchy.formulate`: `flow.sum(model, id=, summands=, total=)` | `flow.sum(model=, id=, summands=, total=)`, and the same for `discount`, `pv`, `interest`, `scale`, `accumulate`, `resample`, `compound`, `linear` and `formulate(hierarchy=, ...)` |
| `model` | `definitions.measure(items, id)`, and the same for `taxonomy`, `classification`, `descendants`, `function`, `find_measures` and `find_classifications`; `provenance.fact_for(model, target)`, `locations(model, claim_id)`; `expression.text.parse(text, names=)`, `render(expression, name=)` | `measure(items=, id=)`, `fact_for(model=, target=)`, `locations(model=, claim_id=)`, `parse(text=, names=)`, `render(expression=, name=)` |
| `model` | `expression.tokens.Token(kind, text, start, end)`, `expression.syntax.Spelling(symbol, operator, precedence)` | `Token(kind=, text=, start=, end=)`, `Spelling(symbol=, operator=, precedence=)` |
| `specification` | `Specification(record, model=, resolver=)` | `Specification(record=, model=, resolver=)` |
| `run` | `rk.run.validate(run, resolver=, units=)` | `rk.run.validate(run=, resolver=, units=)` |
| `execution` | `resolve_cases(specification, resolver=)`, `validate(composition, resolver=, units=)`, `bind_roles(validation)`, `build_problem(binding, limits=)` | `resolve_cases(specification=, resolver=)`, `validate(composition=, resolver=, units=)`, `bind_roles(validation=)`, `build_problem(binding=, limits=)` |
| `execution` | `Overlay(resolver, models=, runs=)` | `Overlay(resolver=, models=, runs=)` |
| `execution` | `rule.evaluate(rules, model=)`, `rule.observe(model, at=, bindings=)` | `evaluate(rules=, model=)`, `observe(model=, at=, bindings=)` |
| `execution` | A backend: `def solve(self, problem, *, limits, remaining, options)` | `def solve(self, *, problem, limits, remaining, options)`; Rangekeeper calls `solve(problem=, ...)` |

### Date fixes

A Specification can fix a date Value: `fix(start_date=date(2027, 1, 1))` or
`fix(b_open=rk.duration.NEVER)`
([#280](https://github.com/daniel-fink/rangekeeper/issues/280)). The stored
`Assignment` then has `date` or `never` and no `quantity`, so `quantity` is now
optional: an Assignment has exactly one of the three. 1.0.0a2 documents stay
valid. Code that reads `assignment.quantity` handles None for a date fix. A
date Value that is not fixed is free, as a number is; in 1.0.0a2 a date Value
could not have a role.

### Underdetermined solves

An underdetermined solve no longer has an output by default (ADR-016,
[#152](https://github.com/daniel-fink/rangekeeper/issues/152)). Its Run records
the solution `underdetermined`, not `feasible`, and `execute` stores no output
Model. `Outcome.status` is `UNDERDETERMINED` as before, and
`Outcome.free_unknowns` still names the free unknowns. `outcome["key"]` raises
the error of `raise_for_status()`. Code that read one candidate value of an
underdetermined solve passes
`config=rk.execution.ExecutionConfig(allow_underdetermined=True)`, or fixes as
many of the free unknowns as the equations lack. A Run that 1.0.0a2 wrote, with
the solution `feasible` and an `underdetermined` diagnostic, still reads as
`UNDERDETERMINED`; nothing needs conversion.

### Flow differences

`Flow.difference(initial=None)` is now `Flow.diff()`, the reverse of
`Flow.cumulative()` (D2, D21,
[#275](https://github.com/daniel-fink/rangekeeper/issues/275)). The first
Movement is its amount less zero; `difference()` made it unresolved. For another
opening value, subtract it in the first Period:
`flow.diff() - rk.flow.Flow(amounts={first_period: opening}, units="AUD")`. See
[running totals](../reference/calculations.md#running-totals-date-masks-and-extremes).

### Movement identity

One rule gives Movement IDs for every transform
([#162](https://github.com/daniel-fink/rangekeeper/issues/162)): a transform keeps
the ID of each Movement that it selects or converts, and gives a fresh ID to each
Movement that it calculates. `Stream.dated()` follows it now: each period amount
that it dates is a new Movement with a fresh ID. Code that found a dated
Movement by the ID of its period Movement must match it by coordinate. See
[the rule](../reference/identity.md#one-rule-for-transforms).

### Model entities

`Model.entity(id=, code=, name=)` returns a read-only `ModelEntity`, not the
generated `Entity` record
([#282](https://github.com/daniel-fink/rangekeeper/issues/282), D44). Its
`record` is the record, and `id`, `code`, `name` and `classification` are the
record's fields; `values` is a Table of the entity's Values with their units,
declared or inferred. Code that used the record reads `record`:

| Before | Now |
| --- | --- |
| `model.entity(code="project").characteristics.values` | `model.entity(code="project").record.characteristics.values` |
| `model.entity(id=id) == record` | `model.entity(id=id).record == record` |
| `isinstance(model.entity(id=id), Assembly)` | `isinstance(model.entity(id=id).record, Assembly)` |

A Value that a draft infers from its equations is stored with `inferred: true`;
a declared Value has no such field. Documents of earlier releases have none,
so their Values read as declared.

### False fixed predicates

A predicate whose values are all fixed and that is false, such as `a > b` with
`a` and `b` fixed and `a` the smaller, now makes the solve `INFEASIBLE`, as a
false constraint does (ADR-016,
[#153](https://github.com/daniel-fink/rangekeeper/issues/153)). In 1.0.0a2 a
false fixed strict comparison was `UNSUPPORTED`. A fixed `!=`, `or` or `not`
predicate, which 1.0.0a2 refused, is now decided too. Code that read
`UNSUPPORTED` for a false fixed predicate reads `INFEASIBLE`.

### Profiles of an amount per year

A growth profile of an amount per unit of time gives each Period that amount
times the Period's length
([#500](https://github.com/daniel-fink/rangekeeper/issues/500)).
`Flow.from_profile(profile=rk.profile.Constant(), periods=quarters,
initial="1e6 AUD pa")` gave a Flow in `AUD pa` with `1e6` in each quarter; it now
gives a Flow in `AUD` with `250e3` in each quarter, and over yearly Periods
`1e6 AUD` in each year. `rx.profile.*` in equations gives the same units. A plain
amount, such as `"100 USD"`, does not change. A distribution profile of a total
per unit of time now raises `UnitError`: give the total as an amount. Code that
read such a Flow as amounts per year reads it as the amount of each Period. See
[amounts per year](../reference/calculations.md#amounts-per-year).

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
| `series.resample(flow, periods=, method=)` | `flow.resample(periods=, method=)` returns a Flow; `Stream.resample` also gives coverage. `flow.split(periods=)` divides amounts over shorter Periods |
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
| `model.system.reduction.AggregateEntry`, `Coverage`, `CoverageStatus` | Unchanged | `rangekeeper.model.system.RollupEntry`, `Coverage`, `CoverageStatus` ([#158](https://github.com/daniel-fink/rangekeeper/issues/158)); `Coverage.undecided` lists the owners that a `Filter` contributor rule could not decide; missing values never count as zero, and `FlowRollup` refuses `MissingValueHandling.ZERO` ([#157](https://github.com/daniel-fink/rangekeeper/issues/157)) |
| `model.system.Pivot`, `PivotColumn`, `Partition` | Unchanged | `pivot(..., label=)` splits the columns by a label key; `PivotColumn.aggregation` becomes `result` ([#158](https://github.com/daniel-fink/rangekeeper/issues/158), [#159](https://github.com/daniel-fink/rangekeeper/issues/159)) |
| `model.system.classified`, `Model.descendants` | Unchanged | — |
| `model.system.reducers` | Unchanged | Removed: the `Reducer` enum replaces it ([#158](https://github.com/daniel-fink/rangekeeper/issues/158)) |
| `shared.units.UnitSystem`, `default_units` | `rangekeeper.quantity.UnitSystem`, `default_units` (the codemod moves them). `Model.unit_system` is unchanged | — |
| `model.measure.Quantity`, `model.Quantity` | `rangekeeper.Quantity` and `rangekeeper.quantity.Quantity` (the codemod moves them) | Quantity text in API arguments ([#255](https://github.com/daniel-fink/rangekeeper/pull/255) D13, D16) |
| `model.system.System`, `Entity`, `Assembly`, `Relationship` | `rangekeeper.model` only (the codemod moves them). `model.system` keeps the views, rollups and pivots | — |
| `model.characteristics.value`, `label` | Removed. `Model.value(owner=, key=)` and `Model.label(owner=, key=)` raise `MissingReferenceError` for a missing key | — |
| `rangekeeper.Model`, `model.Definitions` | Unchanged; the Model format is 1.0.0 | Builder names ([#255](https://github.com/daniel-fink/rangekeeper/pull/255) D6, D16) |
| `io.bundle.Reader`, `write`, `Reader(..., check_index=False)` | `io.bundle.Reader` and `write`, with option values: `Reader(..., index=IndexCheck.SCHEMA)`, `limits=ReadLimits(...)`; `write(..., geometry=GeometrySources(...), parquet=ParquetOptions(...))` (Bundle options, below; [#411](https://github.com/daniel-fink/rangekeeper/issues/411)). A Bundle with 0.x documents does not open | Identifiers `rangekeeper.bundle/1` and `rangekeeper.parquet/1`; the format freezes at 1.0.0b1 (ADR-017) |

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
| `rangekeeper.flow._flow` | `rangekeeper.flow.flow` | agreed | Import `Flow` and `Movement` from `rangekeeper.flow`. |
| `rangekeeper.flow._options` | `rangekeeper.flow.options` | agreed | Import the options from `rangekeeper.flow`. `FlowAggregate` moves to `rangekeeper.flow.aggregation`. |
| `rangekeeper.flow._table` | `rangekeeper.flow.table` | agreed | `rangekeeper.flow` exports `StreamTable`, the type that `display()` returns. |
| `rangekeeper.finance._valuation` | `rangekeeper.finance.valuation` | agreed | Import `pv`, `npv`, `irr` and `payment` from `rangekeeper.finance`. |
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
| `rangekeeper.model.system.reduction` | `rangekeeper.model.system` | agreed | `QuantityRollup` and `FlowRollup` replace `Reduction`; see the symbol entries. The rollup classes are exported by `rangekeeper.model.system`; the `rollup` module that defines them is internal (#391). |
| `rangekeeper.model.scope` | `rangekeeper.model._scope` | agreed | Internal. The checks over raw mappings become private; the typed target lookups move to `rangekeeper.model.targets`. |
| `src/tests/` | `tests/` | agreed | The pass moves the suite to the top level. #177 adds the sub-folders that mirror the packages, and tests/contracts, tests/integration and tests/walkthrough. |

### Renamed names

| Current | 1.0 | Status | Notes |
| --- | --- | --- | --- |
| `rangekeeper.calculations.series.Aggregation` | `FlowAggregate` | draft |  |
| `rangekeeper.model.system.reduction.Aggregation` | `RollupResult` | draft |  |
| `rangekeeper.model.system.reduction.Reduction` | `rangekeeper.model.system.QuantityRollup` | agreed (needs refactor) | The scalar and Flow modes split. `Reduction(select=select_value(key), reducer=reducers.sum, units=)` becomes `QuantityRollup(key=, units=, reducer=Reducer.SUM)`; `Reduction.flows(key=, aggregation=, ...)` becomes `FlowRollup(key=, reducer=, ...)`. Both default to `Contributor.LEAVES`; the scalar default was every node. Custom selectors and reducers are removed. |
| `rangekeeper.model.system.reduction.AggregateEntry` | `rangekeeper.model.system.RollupEntry` | agreed | `aggregate` is the word for combining Flows (D38). |
| `rangekeeper.model.system.errors.AggregationError` | `RollupError` | agreed | `aggregate` is the word for combining Flows (D38). Its code is `Code.ROLLUP`, with the text `rollup`. |
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
| `rangekeeper.execution.compiler.compile` | `rangekeeper.execution.build_problem` | agreed | `build_problem(binding=, limits=)` also checks the symbol and constraint limits; `constraint_limit=` is replaced by `limits=`. |
| `rangekeeper.execution.preparation.Prepared` | `rangekeeper.execution.Binding` | agreed | The typed result of the bind-roles stage. |
| `rangekeeper.execution.publication.candidate` | `rangekeeper.execution.make_candidate` | agreed |  |
| `rangekeeper.execution.acceptance.check` | `rangekeeper.execution.verify` | agreed |  |
| `rangekeeper.execution.acceptance.Acceptance` | `rangekeeper.execution.Verification` | agreed |  |
| `rangekeeper.model.scope.target_value` | `rangekeeper.model.targets.target_value` | agreed |  |
| `rangekeeper.model.scope.target_units` | `rangekeeper.model.targets.target_units` | agreed |  |
| `rangekeeper.model.scope.recorded_scalar` | `rangekeeper.model.targets.recorded_scalar` | agreed |  |
| `rangekeeper.quantity.minor_unit` | `rangekeeper.money.minor_unit` | agreed | The money module owns the ISO 4217 catalogue, boundaries and rounding. |
| `rangekeeper.flow.ResamplingMethod` | `ResampleMethod` | agreed | `Flow.split` and `Stream.split` divide amounts over shorter Periods; `ResampleMethod` has no SPLIT member (#405). |
| `rangekeeper.model.expression.Criterion` | `rangekeeper.model.Criterion` | agreed | `rangekeeper.model` exports the query Filter with its Criterion and ValueTest records. |
| `rangekeeper.model.expression.Direction` | `rangekeeper.model.Direction` | agreed | A fixed word that rangekeeper defines is an enum with one public path. |
| `rangekeeper.run.Status` | `RunStatus` | agreed | The record at `run.report.status`, with `completion` and `solution`. `rk.execution.Status` is the Status of an Outcome, a different type. |
| `rangekeeper.schema.records.Status` | `RunStatus` | agreed (needs schema) | The generated record; the LinkML class is `RunStatus`. Stored Runs do not change. |
| `rangekeeper.model.expression.authoring.sum` | `add_all` | agreed | The name shadowed a builtin. `authoring` is provisional, not 1.0 API (#309): write equations as text, or with `rangekeeper.expressions` (`rx`) on entity handles (#255 D32). |
| `rangekeeper.execution.compiler.Compiled.prepared` | `binding` | agreed |  |
| `rangekeeper.model.system.view.View.aggregate` | `rollup` | agreed | Each use needs review. `view.aggregate(reduction)` becomes `view.rollup(definition=rollup)`. |
| `rangekeeper.model.system.pivot.PivotColumn.aggregation` | `result` | agreed | Each use needs review. |
| `rangekeeper.shared.codes.Code.AGGREGATION` | `ROLLUP` | agreed | `rk.errors.Code.AGGREGATION` (`aggregation`) becomes `Code.ROLLUP` (`rollup`). Stored diagnostics keep the text they recorded. |
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
| `rangekeeper.model.system.errors.HierarchyError.ids` | `targets` | agreed | Each use needs review. Every error has `targets`. `HierarchyError(code, message, ids=)` becomes `HierarchyError(message, code=, targets=)`: the message comes first and each field is a keyword. |
| `rangekeeper.shared.errors.PublishedFileError.path` | `file` | agreed | Each use needs review. `path` of every error is a JSON Pointer. `PublishedFileError(path, error)` becomes `PublishedFileError(message, file=)`; the OSError is the cause. |
| `rangekeeper.flow.flow.Flow.difference` | `diff` | agreed | Each use needs review. `flow.diff()` takes no `initial=`: the first Movement is its amount less zero, not unresolved, so `flow.cumulative().diff() == flow`. For another opening value, subtract it in the first Period: `flow.diff() - rk.flow.Flow(amounts={first_period: opening}, units=)`. |
| Any call: `start_inclusive=` | `start=` | agreed |  |
| Any call: `end_exclusive=` | `end=` | agreed |  |
| `rangekeeper.specification.policy.evaluation.evaluate`: `policy=` | `rules=` | agreed |  |
| `rangekeeper.model.flux.Stream.select`: `labels=` | `names=` | draft |  |
| `rangekeeper.model.flux.Stream.from_values`: `labels=` | `names=` | draft |  |

### Removed names

| Current | Use instead | Status |
| --- | --- | --- |
| `rangekeeper.flow.MeanWeighting` | `ResampleMethod.MEAN` for `MeanWeighting.OBSERVATIONS` and `ResampleMethod.ELAPSED_MEAN` for `MeanWeighting.ELAPSED`. `resample`, `FlowRollup` and `formulation.flow.resample` take no `weighting=` | agreed |
| `rangekeeper.flow.ResampleMethod.SPLIT` | `flow.split(periods=)` or `flow.split(frequency=)`, and `Stream.split` | agreed |
| `rangekeeper.duration.Frequency.BIWEEK` | `offset(..., frequency=Frequency.WEEK, count=2)` for a 14-day step, or explicit 14-day Periods for a grid. There is no fortnight frequency | agreed |
| `rangekeeper.duration.make_period` | `Period(start=, end=)` | agreed |
| `rangekeeper.duration.make_periods` | `Periods(start=, frequency=, count=, month_roll=)`. It returns a `Periods`, not a tuple: compare it with another `Periods`, and use `tuple(periods)` for a tuple | agreed |
| `rangekeeper.duration.periods_between` | `Span(start=, end=).periods(frequency=, include_partial=, month_roll=)`, which returns a `Periods`. A Span is not empty, so the start must be before the end | agreed |
| `rangekeeper.duration.Span.from_duration` | `Span(start=, length="10 years", name=)`, or `Periods(start=, frequency=, count=, month_roll=).span` for a half-year, a decade or another `MonthRoll` | agreed |
| `rangekeeper.model.system.reducers` | The `rangekeeper.model.system.Reducer` enum: `SUM`, `MEAN`, `MIN`, `MAX` and `COUNT`, passed as `reducer=` to `QuantityRollup` or `FlowRollup` | agreed |
| `rangekeeper.calculations.account` | Compose the funding with Flows: a balance is `cumulative()`. Interest is `rk.finance.interest(balance=, rate=)` on known values, and `rx.finance.interest(balance=, rate=)` in an equation (#255 D2, D23, #278). A how-to recipe follows (#194) | agreed |
| `rangekeeper.model.formulation.account.schedule` | Equations over Flows, such as `funding_need = -(net_cash_flow + loan_interest).cumulative()`. A Model declares no account (#255 D2) | agreed |
| `rangekeeper.model.formulation.authoring.declare` | `rk.Model(name=)`, `model.edit()` and entity handles with `value(key=, units=)`, `flow(...)`, `date(...)` and `equations(...)` (#255 D6, D16) | agreed (needs refactor) |
| `rangekeeper.calculations.series.align` | Stream(flows, join=, missing=).align() | agreed |
| `rangekeeper.calculations.series.multiply` | Flow.multiply(*others) | agreed |
| `rangekeeper.calculations.series.integrate` | Flow.integrate(exposures=, units=) and Flow.integrate_time(day_count=, units=) | agreed |
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
| `rangekeeper.execution.executor.Executor` | `rangekeeper.execution.execute(specification=, store=, config=)`, which returns an `Outcome`; read the Run as `outcome.run`. Use `rangekeeper.execution.solve(specification=, config=)` to write nothing | agreed |
| `rangekeeper.execution.publication.CandidateResolver` | `rangekeeper.execution.Overlay(resolver=, models=, runs=)` | agreed |
| `rangekeeper.execution.planning.Plan` | `rangekeeper.execution.resolve_cases(specification=, resolver=)`. It returns `Cases`, which is also a resolver | agreed |
| `rangekeeper.execution.preparation.prepare` | `rangekeeper.execution.validate(composition=, resolver=, units=)`, then `rangekeeper.execution.bind_roles(validation=)` | agreed |
| `rangekeeper.shared.errors.BoundaryError` | rangekeeper.errors.RangekeeperError | agreed |
| `rangekeeper.shared.errors.ValueEncodingError` | rangekeeper.errors.EncodingError | agreed |
| `rangekeeper.io.atomic` | `rangekeeper.io.json.write` and `rangekeeper.io.yaml.write`, which publish a new file atomically | agreed |

### Changes of API shape

These decisions change API shapes, not only names. The codemod does not apply
them; the issues that the table names make the changes.

| Topic | 1.0 | Source |
| --- | --- | --- |
| Quantity text in API arguments | Arguments take unit text such as `"7 % pa"`; `per` divides and `pa` means per year. | #255 D13, D16, D17 |
| Execution configuration | `Executor(store, backend=, units=, tolerances=)` becomes `execute(specification=, store=, config=ExecutionConfig(backend=, units=, tolerances=))`. `ExecutionConfig` also holds the default `limits` and the `backend_options`. | ADR-013, #128 |
| Execution calls | The arguments of `rk.execution.solve`, `execute`, `assemble`, `assemble_batch`, `make_candidate` and `verify` are keyword-only: `solve(specification, store)` is now `solve(specification=, resolver=)`, and so are the stage calls `resolve_cases(specification=, resolver=)`, `validate(composition=, resolver=, units=)`, `bind_roles(validation=)` and `build_problem(binding=, limits=)`, the rule calls `rk.execution.rule.evaluate(rules=, model=)` and `observe(model=, at=, bindings=)`, `Overlay(resolver=, models=, runs=)` and `rk.run.validate(run=, resolver=)`. A backend declares `def solve(self, *, problem, limits, remaining, options)`. The records of `rk.execution`, `rk.execution.backends` and `rk.execution.rule` take keyword arguments only, for example `Limits(time_limit=)`, `Tolerances(absolute=, relative=)` and `BackendResult(termination=, candidate=)`. | #255 D14, #410 |
| Resample options | `resample(method=)` takes one `ResampleMethod` for each line, and the weighting of a mean is part of the method: `MEAN` or `ELAPSED_MEAN`. `split(periods=)` or `split(frequency=)` divides amounts over shorter Periods and takes no `method=` or `missing=`. | #399, #405 |
| Flow and Stream options | Each argument chooses one thing. `flow.check(resolved=True)` is `flow.require_resolved()`. `clean(remove_zeroes=True)` is `clean().drop_zeroes()`; `extent()` takes no flag. `round(mode=)` takes a `rangekeeper.money.RoundingMode`. `collapse(on=)` takes a date or a `PeriodTiming` (was `timing=`). `integrate(day_count=)` is `integrate_time(day_count=)`. `from_periods` and `from_events` take no `dates=` or `ids=`: make the `Movement` records. `multiply` and `scale` follow `*`, so an unresolved amount gives an unresolved product. `Stream.select(value_ids=)` is `Stream.select_values(ids)`. The `missing` and `join` policies live on the Stream: `Stream(..., missing=, join=)` or `stream.with_policy(missing=, join=)`; `aggregate`, `sum`, `min`, `max` and `resample` take no `missing=` or `join=`. `sum(timing=)` is `stream.dated(timing=).sum()`. | #399, #406 |
| Keyword-only arguments | Every Rangekeeper call names its arguments. | #255 D14 |
| Model authoring and builder names | `rk.Model(name=)`, `model.edit()`, `ModelDraft.add_entity(code=)` and entity handles. `Model(record, units=)` is removed: `rk.Model(name=)` makes an empty Model, and `Model.create(...)` or `Model.from_data(...)` take complete records (#141, #281). | #255 D6, D16, D18 |
| Specification calls | `fix`, `free`, `cases`, `across` and `parameters` each return a new Specification; unfixed values are free. `model.specify(name=)` makes one. `fix(target, quantity, id=, model=, ids=, recorded=)` is now `fix(key=quantity)`, or `fix({target: quantity})` for a dotted path, a UUID or a mapping of Movement UUIDs; `free(target, id=, model=, ids=)` is now `free(*targets)`. The Specification keeps its Model: pass `Specification(record=, model=, resolver=)` for a record. `recorded=True` is removed: fix the recorded Quantities explicitly (#144). `fix` also takes Quantity text and a number for a ratio; a number for a value with other units raises `UnitError`, not `TypeError`. `specify` and each call record as unknowns the values that the equations use and that nothing fixes, so `free` is needed only to release a fixed value. `roles` lists the role of each value as an `rk.specification.Role` (#290). | #255 D7, D8 |
| Loan payment | `rangekeeper.finance.payment(principal=, rate=, term=, frequency=)` (#167). | #255 D19 |
| Funding accounts | There is no account class and no account declaration. A balance is `cumulative()` of a Flow. | #255 D2, D23 |
| Growth and distribution profiles | `rk.profile.Constant`, `Linear`, `Compounding`, `Uniform` and `SCurve` with `rk.flow.Flow.from_profile(profile=, periods=, initial= or total=)` replace `extrapolate`, `distribute` and `GrowthMethod` (#303). | #255 D12 |
| Market paths | `rk.market.Dynamics`, `rk.market.generate` and `rk.market.Paths` replace the scenario plan and the trend and cycle kernels (#298, #299). | #255 D29, D31 |
| Fixed words are enums | Diagnostic codes are `rk.errors.Code` (#154); "the event does not happen" is `rk.duration.NEVER`; `Role`, `DecisionResult`, `Status` and `Direction` are enums. Words that the data defines stay strings. | #255 D26 |
| Date shift | `rk.duration.shift(value, by=)` is now `shift(on=, by=)`. `rk.duration.DateValue` (a date or `NEVER`) names its type. `shift` moves a date value by a length; `offset(value=, frequency=, count=, month_roll=)` moves a date by whole steps of a Frequency. | #255 D14, D25, #389 |
| Calendar grids | `containing_period(value, *, frequency=, week_start=, year_start_month=, origin=)` is now `containing_period(*, on=, grid=)`. The grid is `DayGrid()`, `WeekGrid(starts=calendar.Day.MONDAY)`, `MonthGrid(frequency=, year_starts=calendar.Month.JANUARY)` for months, quarters, half-years and years, or `MultiYearGrid(frequency=, origin=)` for bienniums, quinquenniums and decades. A grid takes only the choices that apply to it; a week grid takes no origin. | #399, #403 |
| Keyword-only arguments in quantity, money and duration | Name each argument: `UnitSystem(currencies=, definitions=)`, `UnitSystem.convert(quantity=, to=)`, `register(name=, definition=, aliases=)`, `alias(alias=, unit=)`, `rk.money.round(amount=, currency=, places=, mode=)`, `rk.duration.offset(value=, frequency=, count=, month_roll=)` and `cover(periods=, name=)`. A natural pair stays positional: `compatible(left, right)`, `multiply(left, right)`, `divide(numerator, denominator)`, `count_steps(start, end, frequency=)` and `year_fraction(start, end, convention=)`. | #410 D14 |
| Bundle options | `rk.io.bundle.write(root=, model=, documents=, resolver=, geometry=, parquet=)` and `Reader(root=, providers=, limits=, index=)`. `geometry=GeometrySources(directories={model_id: path}, providers={(provider, format, format_version): adapter})` replaces `geometry=`, `geometries=`, `provider=` and `providers=` of `write`; a pin with no provider uses `rk.io.geometry_providers`. `parquet=ParquetOptions(compression=, row_group_size=)` replaces `compression=` and `row_group_size=`. `limits=ReadLimits(documents=, bytes=, rows=)` replaces `max_documents=`, `max_bytes=` and `max_rows=`; `index=IndexCheck.SCHEMA` replaces `check_index=False`. `Reader` has no `provider=`. | #411, #422 |
| Keyword-only arguments in io and the extension registries | Name each argument: `rk.io.json` and `rk.io.yaml` `loads(text=, kind=)`, `read(path=, kind=)` and `write(document=, path=)`; `rk.io.bundle.write(root=, model=, ...)` and `Reader(root=, ...)`; `rk.io.polars.dates(flow=, ...)` and `from_frame(frame=, units=)`; `GeometryProvider.validate(path=, geometry=)`, so a provider declares `def validate(self, *, path, geometry)`; and `register(name=, implementation=)` on `unit_systems`, `geometry_providers`, `profiles` and the execution backends `registry`. The store protocol stays positional: `put(document)` and `load_model(id)`, `load_specification(id)` and `load_run(id)`. | #410 D14 |
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
