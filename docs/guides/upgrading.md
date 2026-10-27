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

The codemod applies the [rename map](#100a2-rename-map-draft) to code that uses
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
| `from rangekeeper.model.characteristics import Value` (and `Label`, `Characteristics`, `ValueKind`) | `from rangekeeper.model import Value`. `model.characteristics` keeps only `value()` and `label()` |
| Code that reads the wire keys `start_inclusive` and `end_exclusive` | The keys are `start` and `end` |

The codemod does not apply the entries that wait for decisions in
[#255](https://github.com/daniel-fink/rangekeeper/pull/255), for example `pv`,
`npv`, `irr`, growth profiles and the builder names. The
[decisions under review](#decisions-under-review) table lists them. A later
release changes these names.

### Document formats 1.0.0

Release 1.0.0a2 resets the Model, Specification and Run formats, and every schema
module, to 1.0.0 ([ADR-017](../decisions/017-api-and-formats.md)). A 1.x reader
reads every format with major version 1, up to its own version. It does not read
0.x documents: Model 0.7.0 and 0.8.0, Specification 0.7.0 and Run 0.4.0 raise
`UnsupportedVersionError`. `rangekeeper.io.migration` and `model_07_to_08` are
removed. Period and Span store `start` and `end`. Model revision identities and
the computation fingerprints change once.

For each stored 0.x document or Bundle, choose one route:

- rebuild it from its source pipeline with 1.0.0a2;
- convert it with the one-off conversion script
  ([#120](https://github.com/daniel-fink/rangekeeper/issues/120)) when it is available.

Never rewrite the old artifact in place. A scenario realization saved before
1.0.0a2 stays readable as data, but `replay` raises `ReplayUnavailableError` for
it; generate it again.

### Breaking surface for 1.x consumers

This table lists the public names that 1.x consumers use, with their state in
1.0.0a2 and the change that follows before 1.0.0
([#217](https://github.com/daniel-fink/rangekeeper/issues/217)).

| 1.0.0a1 name | 1.0.0a2 | Before 1.0.0 |
| --- | --- | --- |
| `model.system.View` | Unchanged | A declarative `Filter` adds data filters ([#121](https://github.com/daniel-fink/rangekeeper/issues/121)) |
| `model.system.Hierarchy` | Unchanged | — |
| `model.system.Reduction`, with `execute`, `pivot`, `Contributor` and callable contributors | Unchanged | Splits into `QuantityRollup` and `FlowRollup` with one reducer enum (ADR-012, draft) |
| `model.system.reduction.Aggregation` | `RollupResult` (the codemod renames it) | — |
| `calculations.series.Aggregation` | `rangekeeper.flow.FlowAggregate` (the codemod renames it) | — |
| `model.system.reduction.AggregateEntry`, `Coverage`, `CoverageStatus` | Unchanged | Missing values never count as zero ([#157](https://github.com/daniel-fink/rangekeeper/issues/157)) |
| `model.system.Pivot`, `PivotColumn`, `Partition` | Unchanged | A Pivot can use a label key for its columns (ADR-017) |
| `model.system.classified`, `Model.descendants` | Unchanged | — |
| `model.system.reducers` | Unchanged | Part of the `Reduction` split |
| `shared.units.UnitSystem`, `default_units` | `rangekeeper.quantity.UnitSystem`, `default_units` (the codemod moves them). `Model.unit_system` is unchanged | — |
| `model.measure.Quantity` | `rangekeeper.Quantity` and `rangekeeper.quantity.Quantity` | Quantity text in API arguments ([#255](https://github.com/daniel-fink/rangekeeper/pull/255), pending) |
| `rangekeeper.Model`, `model.Definitions` | Unchanged; the Model format is 1.0.0 | Builder names ([#255](https://github.com/daniel-fink/rangekeeper/pull/255), pending) |
| `io.bundle.Reader`, `write`, `Reader(..., check_index=False)` | Unchanged API. A Bundle with 0.x documents does not open | Identifiers `rangekeeper.bundle/1` and `rangekeeper.parquet/1`; the format freezes at 1.0.0b1 (ADR-017) |

Three routes help a 1.x consumer:

- the consumer codemod, above;
- deterministic builds with a namespace, as a tested contract
  ([#147](https://github.com/daniel-fink/rangekeeper/issues/147)), so that a
  rebuild from source pipelines gives the same identities each time;
- rebuild or convert for stored Bundles
  ([#120](https://github.com/daniel-fink/rangekeeper/issues/120)).

## 1.0.0a2 rename map (draft)

This section is a draft. Release 1.0.0a2 moves modules into the 1.0 layers and
applies the glossary names in one pass
([ADR-010](../decisions/010-layers-and-packages.md),
[ADR-012](../decisions/012-naming-and-glossary.md)). The
[codemod](../../tools/codemod/README.md) applies this map. The map file
[`tools/codemod/rename_map.yaml`](../../tools/codemod/rename_map.yaml) is the source
of these tables.

Each entry has a status:

- **agreed**: an accepted ADR gives the 1.0 name.
- **draft**: the ADR gives the direction, and the map proposes the exact name.
  [#93](https://github.com/daniel-fink/rangekeeper/issues/93) finalises it.
- **pending**: the name depends on a decision under review in
  [#255](https://github.com/daniel-fink/rangekeeper/pull/255), the proposed
  walkthrough cells. The codemod does not apply it.
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
| `rangekeeper.schema.behaviors.flow` | `rangekeeper.flow.behavior` | draft (needs refactor) | The generated Flow and Movement records load these behaviours, so the schema runtime must find them in `flow` without an upward import. |
| `rangekeeper.calculations` | `rangekeeper.finance` | agreed |  |
| `rangekeeper.calculations.projection` | `rangekeeper.finance.growth` | pending | #255 D12: growth and distribution profiles move to `rangekeeper.profile`, applied by `Flow.from_profile`. |
| `rangekeeper.run.execution` | `rangekeeper.execution` | agreed |  |
| `rangekeeper.specification.policy.evaluation` | `rangekeeper.execution.policy` | draft (needs refactor) | The lazy exports of `specification.policy` load it by its short name. |
| `rangekeeper.shared.units` | `rangekeeper.quantity` | draft | The namespace that holds the unit system, the registry and `isclose` is `rangekeeper.quantity`, so "units" keeps one meaning: a unit string. `Quantity` is also at the root. |
| `rangekeeper.io.store` | `rangekeeper.shared.store` | draft (needs refactor) | The protocol imports Model, Specification and Run; these imports must become type-only. |
| `rangekeeper.model.system.projection` | `rangekeeper.model.system.table` | draft |  |
| `rangekeeper.model.scenario` | `rangekeeper.finance.paths` | draft (needs refactor) | Path generators and the MarketPaths document replace the scenario plan. |
| `src/tests/` | `tests/` | agreed | The pass moves the suite to the top level. #177 adds the sub-folders that mirror the packages, and tests/contracts, tests/integration and tests/walkthrough. |

### Renamed names

| Current | 1.0 | Status | Notes |
| --- | --- | --- | --- |
| `rangekeeper.calculations.series.Aggregation` | `FlowAggregate` | draft |  |
| `rangekeeper.model.system.reduction.Aggregation` | `RollupResult` | draft |  |
| `rangekeeper.model.system.reduction.Reduction` | `QuantityRollup` | draft (needs refactor) | The scalar and Flow modes split into QuantityRollup and FlowRollup, with one Reducer enum. |
| `rangekeeper.model.duration.calendar.measure` | `count_steps` | draft |  |
| `rangekeeper.model.duration.period.align` | `containing_period` | draft |  |
| `rangekeeper.model.measure.Quantity` | `rangekeeper.quantity.Quantity` | draft | `rangekeeper.Quantity` at the root also gives the record. |
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
| `rangekeeper.calculations.financial.calculate_pv` | `pv` | pending | #255 D14 and D19 with #167: `rangekeeper.finance.pv(flow=, rate=, on=)`. |
| `rangekeeper.calculations.financial.calculate_xnpv` | `npv` | pending | #255 D19 with #167: `rangekeeper.finance.npv(flow=, rate=, on=)`. |
| `rangekeeper.calculations.financial.calculate_irr` | `irr` | pending | #255 D4 with #164: `rangekeeper.finance.irr`, also an equation function. |
| `rangekeeper.calculations.projection.project_values` | — | pending | #255 D12: `rangekeeper.flow.Flow.from_profile(profile=, periods=, initial=)` with `rangekeeper.profile` growth profiles. |
| `rangekeeper.calculations.projection.distribute` | — | pending | #255 D12: `Flow.from_profile(profile=, periods=, total=)` with `rangekeeper.profile.Uniform` or `SCurve`. |
| `rangekeeper.calculations.projection.ProjectionMethod` | — | pending | #255 D12: profile classes replace the method enum; the word projection is not used. |
| `rangekeeper.model.expression.authoring.sum` | — | pending | #255 D6 and D18: equation strings on entity handles replace the expression builders. ADR-012 forbids public names that shadow builtins. |
| `rangekeeper.model.formulation.authoring.declare` | — | pending | #255 D6 and D16: `rk.Model(name=)`, `model.edit()` and entity handles with `value(key=, units=)`, `flow(...)` and `date(...)`. |
| `rangekeeper.specification.specification.Specification.lock` | `fix` | agreed |  |
| `rangekeeper.specification.specification.Specification.unlock` | `free` | agreed |  |
| `rangekeeper.schema.records.Period.start_inclusive` | `start` | agreed | Also Span. Half-open; the end is excluded. The package pass changed the schema in 1.0.0a2 (#119), so the consumer pass applies this entry. |
| `rangekeeper.schema.records.Period.end_exclusive` | `end` | agreed | Also Span. |
| `rangekeeper.model.flux.Stream.labels` | `names` | draft | Each use needs review. Classification `labels` keep their name. The package pass renamed the Stream field by hand; the consumer pass lists the uses to check. |
| `findings` | `diagnostics` | draft | Each use needs review. |
| `issues` | `diagnostics` | draft | Each use needs review. |
| Any call: `start_inclusive=` | `start=` | agreed |  |
| Any call: `end_exclusive=` | `end=` | agreed |  |
| `rangekeeper.model.flux.Stream.select`: `labels=` | `names=` | draft |  |
| `rangekeeper.model.flux.Stream.from_values`: `labels=` | `names=` | draft |  |

### Removed names

| Current | Use instead | Status |
| --- | --- | --- |
| `rangekeeper.calculations.series.align` | Stream(flows, join=, missing=).align() | agreed |
| `rangekeeper.calculations.series.multiply` | Flow.multiply(*others) | agreed |
| `rangekeeper.calculations.series.integrate` | Flow.integrate(exposures=, day_count=, units=) | agreed |
| `rangekeeper.calculations.series.resample` | Flow.resample(periods, method=) and Stream.resample(periods, method=) | agreed |
| `rangekeeper.calculations.series.aggregate` | Stream.aggregate(method=), Stream.sum(), Stream.min() and Stream.max() | agreed |
| `rangekeeper.calculations.series.Alignment` | The Stream that Stream.align() returns; Stream.aggregate() replaces Alignment.reduce() | agreed |
| `rangekeeper.model.characteristics` | Value and Label access on the owner record; re-exports in rangekeeper.model | agreed |
| `rangekeeper.model.scenario.market.ScenarioPlan` | Path generators and the MarketPaths document | agreed |
| `rangekeeper.model.scenario.market.sample` | Path generators and the MarketPaths document | agreed |
| `rangekeeper.model.scenario.market.capture` | Path generators and the MarketPaths document | agreed |
| `rangekeeper.model.scenario.market.realize` | Path generators and the MarketPaths document | agreed |
| `rangekeeper.model.scenario.market.generate` | Path generators and the MarketPaths document | agreed |
| `rangekeeper.model.scenario.view.Market` | The MarketPaths document | agreed |

### Decisions under review

These decisions change API shapes, not only names. They wait for the review of
the proposed walkthrough cells.

| Topic | Proposal |
| --- | --- |
| Quantity text in API arguments | #255 D13, D16 and D17: arguments take unit text such as `"7 % pa"`; `per` divides and `pa` means per year. |
| Keyword-only arguments | #255 D14: every Rangekeeper call names its arguments. |
| Model authoring and builder names | #255 D6, D16 and D18: `rk.Model(name=)`, `model.edit()`, `ModelDraft.add_entity(code=)` and entity handles. |
| Specification calls | #255 D7 and D8: `fix`, `free`, `cases`, `across` and `decide` each return a new Specification; unfixed values are free. |
| Loan payment | #255 D19 with #167: `rangekeeper.finance.payment(principal=, rate=, term=, frequency=)`. |

<!-- rename-map:end -->

## Upgrade to 0.9

This is a breaking library change.

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

The old Python and C# runtimes, `migration` package and draft schema upgraders are removed.
Current Model, Specification and Run artifacts remain readable. Retained historical source
formats require explicit conversion supplied by the consumer. Historical evidence and source files
remain in the repository. They do not restore removed APIs.

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
