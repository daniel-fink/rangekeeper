# ADR-005 Flux and Stream implementation

Status: implemented and locally verified on 2026-10-08. The first notebook migration
is also accepted; six notebooks remain in that separate phase. See the
[codebase acceptance record](../research/flux-stream-2026-10-08/README.md)
for source hashes, the installed wheel, tests, timings, memory costs and external limits.

Implementation used the actual working tree at `53d9bfa`, preserving existing local
changes. It passed 1,478 tests with 24 existing optional skips, schema and typing
checks, and the installed-wheel Stream and acausal hierarchy examples. The same
equations solve forward and backward, including the specified 220 rent result.

The design and execution plan below are retained as the architectural contract.
The current API references describe the delivered interfaces. The later
[first-notebook acceptance](../research/basic-dcf-2026-10-08/README.md) records its
code, narrative and output migration.

Restore Stream as the main interface for coordinating, displaying, resampling and
combining flows. Use Polars for bulk calculations and reuse prepared columns
through a sequence of Stream operations. Keep canonical Flow and Movement records
as the authoritative Model content in this change.

This plan replaces the earlier conversational proposal to use Stream only as a
collection around the existing calculation functions. It includes changes to the
calculation backend, performance acceptance and the public module name
`rangekeeper.model.flux`. The saved plan is the implementation reference for this
work. Its examples describe the implemented API.

## Problem and baseline

The legacy Stream let a caller collect flows, choose a common frequency, inspect
the constituent line items and calculate a combined Flow. The current API requires
callers to assemble resampling loops, alignment, aggregation and dataframe joins.
This makes simple notebooks harder to read and repeats work in larger models.

At source checkpoint `53d9bfa`, the relevant implementation has these limits:

- `model/flow.py` defines Stream as a selection of Flow Values in one Model
  revision. It cannot collect directly supplied flows or display and resample them.
- `calculations/series.py` uses Polars for joins and grouped arithmetic, but also
  builds Python coordinate mappings, converts results back into records, and
  performs cross-flow reductions in Python. Resampling scans target periods for
  each source movement before constructing its Polars frame.
- Span exists as a named Period. Calendar construction is exposed mainly through
  free functions in `model.duration`.
- `model/system/reduction.py` accepts scalar Measurement Values only. It does not
  aggregate Flow Values through a hierarchy.

Existing local changes outside this plan must be preserved. Refresh the source
checkpoint and dirty-state inventory before implementation and benchmark capture.
Current project commands run from the repository root.

## Accepted design

| Owner | Responsibility |
| --- | --- |
| Flow and Movement | Immutable amounts, coordinates, units, identities and evidence references |
| Span and Period | Named extents, bounded periods and discoverable calendar operations |
| Stream | Ordered labelled flows, collection operations, reusable calculation state and convenient display |
| Calculation backend | Bulk alignment, resampling, aggregation and coverage calculations using Polars where appropriate |
| Presentation adapters | Numeric table projection, HTML and text formatting |
| View and Hierarchy | Model selection and explicit relationship or membership structure |
| Reduction | Reusable contributor selection and scalar or Flow aggregation through a hierarchy |
| Formulation authoring | Passive equations with general structural parameter names and stable symbol references |
| Specification | Per-investigation assignments, unknowns, bounds and explicit lock/unlock authoring |
| Executor and acceptance | Capability checks, solving, independent evaluation and accepted publication |

Rename the public module `model/flow.py` to `model/flux.py`. Export Flow, Movement,
Stream and the relevant existing Flow choices from that module. This does not
rename the Flow schema class, the single-record behaviour module, or passive Flow
formulation authoring merely because their filenames also contain `flow`.

Stream may hold a private Polars calculation representation. This representation
is derived from its inputs or preceding operations; it is not an independently
editable copy of Model content. Operations return new Streams or results. Source
Models and input records remain unchanged.

Keep one authoritative Flow representation in this phase. Flow calculations may
use the same columnar backend when useful, but decoding, persistence and references
continue to use the canonical records. Replacing Flow storage with a dataframe is
a separate redesign to consider only if measurements identify record construction
or storage as a dominant cost.

## Naming review and migration inventory

The review found nine public equation builders with a `result` parameter across
`model/formulation/flow.py`, `growth.py`, `financial.py` and `account.py`. The shared
`aligned` helper also uses directional names. Apply the same general vocabulary to
these builders and the multiple-equation `account.schedule` builder.

Use explicit, discoverable keyword parameters for each mathematical role. This
replaces the earlier tuple-packing and equation-side proposals. General naming
does not mean hiding distinct roles inside `arguments`, a dictionary or numbered
parameters. A collection parameter is appropriate only for one repeated role,
such as the `summands` in a sum.

The governing example is `flow.sum(summands=..., total=...)`. These names
identify quantities in a relationship; they do not make the summands fixed or
the total unknown. A Specification can fix the total and solve one or
more summands. Apply the same rule to a product and its factors, a quotient and
its numerator/denominator, and the variables in a recurrence.

Use general mathematical names in generic builders. Retain recognised relation
names such as `principal` and `rate` in specialised financial/account builders
where they make the signature clearer. Avoid project-specific nouns such as rent
or building income in these APIs. Those belong in the caller's variable names.

| Builder | Planned quantity parameters | Mapping from the current interface |
| --- | --- | --- |
| Binary expression authoring, including `equal` | `left`, `right` | Retain existing names; operand position does not imply solve direction |
| `expression.sum` | `summands` | Current ordered `expressions` collection; one repeated additive role |
| `flow.sum` | `summands`, `total` | `sources` to `summands`; `result` to `total` |
| `flow.scale` | `multiplicand`, `multiplier`, `product` | `source` to `multiplicand`; `factor` to `multiplier`; `result` to `product` |
| `flow.accumulate` | `increments`, `initial`, `accumulation` | `source` to `increments`; retain `initial`; `result` to `accumulation` |
| `growth.compound` | `initial`, `rate`, `series` | Retain `initial` and `rate`; `result` to `series` |
| `growth.linear` | `initial`, `increment`, `series` | Retain `initial` and `increment`; `result` to `series` |
| `financial.discount` | `series`, `rate`, `discounted` | `source` to `series`; retain `rate`; `result` to `discounted` |
| `financial.pv` (renamed from `present_value`) | `sequence`, `value` | `source` to `sequence` (a discounted Flow); `result` to `value` (a scalar Reference) |
| `financial.reversion` | Remove the dedicated helper | Retain the mathematics and explicit temporal mapping as a composed formulation pattern |
| `account.interest` | `principal`, `rate`, `interest` | Retain `principal` and `rate`; `result` to `interest` |
| `account.schedule` | `transactions`, `initial`, `rate`, `balances`, `interest` | Retain `transactions`, `rate`, `interest`; `starting` to `initial`; `closing` to `balances` |
| `flow.aligned` | `members`, `reference` | `sources` to `members`; `result` to `reference`, which determines coordinate order only |
| New `flow.resample` | `sequence`, `resampled` | Flow whose Movements are grouped, and Flow whose periods define those groups |
| New `Reduction.formulate` | `aggregates` | Entity UUID to declared aggregate Flow Value UUID mapping |

Retain operation settings such as `method`, `weighting`, `first_period`, account
conventions and nonnegative-principal requirements. Rename the account schedule's
`balance` setting to `balance_basis` to distinguish its Balance enum from the
`balances` Flow. Reversion's temporal mapping becomes part of the documented
formulation pattern below. Settings describe structure or constraints, not
assignments of participating quantities.

Use plural `summands` because a sum accepts a collection. Name the related Flow
`total`, following the user's refined example. Binary `left` and
`right` are acceptable notation positions and need no migration.

Rename only the passive `model.formulation.financial.present_value` helper to
`pv`. Its `sequence` is already discounted; the helper declares its sum and does
not perform discounting. Prefer `value` over the suggested `measure`: Measure
already names a schema definition of a characteristic and its canonical units,
whereas this parameter refers to a scalar Value. Prefer `resampled` over the
suggested `sequenced`: the latter suggests ordering, while both participating
Flows already have an order. These are naming recommendations; no new numerical
or solver behaviour follows from them.

Give every named parameter its own type annotation and docstring description,
including units and its role in the equation. Preserve current Flow UUID and scalar
Reference types. Use singular names for one participant and plural names for a
collection. A Flow can contain summands across periods, while a Stream can
represent summands across flows; make that distinction clear in the types.
`members`, `elements`, `variables`, `arguments` and `operands` remain useful general
terms, but do not use them to conceal more informative mathematical role names.

The direct maintained formulation builder calls found by import-aware Python inspection are
in `src/tests/test_temporal_execution.py` and `src/tests/test_account_schedule.py`.
The latter also checks preserved declarations against frozen fixtures.
`examples/rangekeeper_examples/investment.py` calls `aligned` positionally in its
resale policy builder. Keep those policy semantics and identity checks intact.
The maintained notebooks inspected do not import these formulation builders
directly; their deferred `model.flow` and calculation-enum migration still applies.

Keep the existing binary expression signatures in `binary`, `add`, `subtract`,
`multiply`, `divide`, `power` and `equal`. Rename only expression `sum`'s collection
parameter to `summands` and update any keyword callers. Keep `literal` and
`reference` construction unchanged. The canonical Expression tree continues to
store the same ordered operands; no tuple-packing API is introduced.

Change signatures, internal structural names, docstrings, error messages,
call sites, typing examples and current reference prose together. Expand changed
multiline signatures according to the contributor guide. Search imports and aliases,
not every textual occurrence of `result`, when locating callers.

Do not rename these distinct concepts:

- `Reference.target`, Assignment targets, `target_value` and target-unit lookup:
  they identify a referenced record, not a solve direction.
- Run outputs, backend candidates, calculation results, adapter inputs/outputs and
  resampling target grids: they describe actual operations or coordinates.
- The schema's ordered `Expression.operands` field and operator semantics. The
  public authoring interface change does not change that representation.
- Local accumulator variables such as `result` in expression-tree construction.
- Saved Value keys, Formulation names, operation keys, binding order, Constraint
  IDs, Expression occurrence IDs or frozen historical fixtures.

Except for the explicit `present_value` to `pv` API rename and retirement of
`financial.reversion`, keep builder function names and generated declaration
content stable for the same IDs and quantities.
Retain the saved `present_value` operation name and its identity derivation; the
Python helper rename does not rename stored Formulations. Do not retain a
`present_value` forwarding alias. Keyword changes must not change
the strings used by `declare`, `identify` or `identify_tree`, or reorder operands
and bindings. Do not add old-keyword aliases. New resampling and hierarchy builders
will have their own explicit identity contracts. No persistent schema change
follows from these names.

### Reversion as a composed formulation pattern

Remove the dedicated `model.formulation.financial.reversion` convenience function
from the planned public helper set. Retain reversion as a modelling concept and a
documented formulation pattern built with existing expressions, references and
`declare`. Do not add a replacement alias or another single-purpose helper.

The current helper returns a Formulation already. Its implementation only checks
the declared Flow shapes and a complete Movement mapping, then declares each
mapped income divided by a capitalization reference. It does not choose a sale
date, infer the next period, select a financial income basis, deduct transaction
costs or decide when a sale is realised. The investment and design example
builders already compose their own reversion equations from ordinary expressions.

Keep three choices explicit in the example pattern:

1. Capitalisation: relate a selected income quantity, a capitalization rate and
   a capitalized value, with compatible units and applicable rate constraints.
2. Temporal mapping: identify which income Movement relates to which value
   Movement. In the current examples, income in period `t + 1` supports a value
   at the end of period `t`; it does not move that value into period `t + 1`.
3. Realisation: if the value becomes sale proceeds, declare the sale event or
   control and its timing separately. A capitalized value is not automatically
   an actual cash-flow receipt.

The existing quotient relationship can be authored directly as
`value[t] = income[t + 1] / rate[t]`, using the selected Movement references.
The pattern can instead use `value[t] * rate[t] = income[t + 1]` when the Model
explicitly enforces an admissible nonzero rate. This product form can remain
affine when one factor is fixed; the current compiler rejects an unknown divisor
in the quotient form. It still does not support a product of two unknown factors.
Do not silently rewrite saved equations: at zero rate the two forms do not have
the same domain. Unknown-rate admissibility needs supported bounds, such as an
explicitly chosen positive lower bound, rather than an unsupported strict test.

The temporal mapping must use declared coordinates and identities. Do not add a
universal one-position shift, wrap the last period to the first, or infer a lag
across different frequencies. Reuse the existing shape/mapping validation and
validate complete reference coverage where the chosen pattern requires it.

Migrate the direct helper call in `test_temporal_execution.py` to a composed
formulation using the existing quotient expressions and explicit mapping, retaining
its numerical and reference checks. Preserve saved `reversion` declarations,
operation names and frozen historical fixtures; generic Formulation decoding does
not require this Python helper. New product-form examples have their own declared
expressions and acceptance checks. Document the pattern in maintained examples
and reference guidance without changing notebook prose in this phase.

## Acausal modelling requirement

The Stream interface must support the wider purpose of defining relationships once
and changing fixed and unknown quantities between investigations. Fast calculation
of recorded amounts is not sufficient evidence of this capability. The following
requirements extend the plan. The naming inventory and examples define the implemented scope.

Preserve the existing Model, Specification and Run boundary:

- Model formulations own equations between Value and Movement references. An
  equation does not permanently designate any participating variable as an output.
- A Specification selects fixed quantities through assignments and quantities to
  solve through unknown references. A recorded amount does not lock a variable.
- Execution compiles the equations after applying those roles, checks backend
  capability, solves, independently checks the candidate and publishes a revision.
- Stream coordinates flows and provides calculation and inspection. Its private
  Polars state is not the authoritative equation representation or a solver.

### Connect collection operations to passive formulations

Provide an explicit formulation-authoring route for Model-backed selections as
well as the known-data calculation route. Reuse the existing
`model.formulation.flow.sum`, `scale` and `accumulate` builders where applicable.
Extend formulation authoring for fixed-grid resampling and hierarchical sums.
Return canonical Formulations that callers can add to a Model through an explicit
revision. Do not create an independent persistent computation graph.

Numeric methods such as `stream.sum()` still return calculated results. The
formulation route instead relates Movement references in an equation without
reading their magnitudes. Keep these choices explicit; do not switch from
calculation to equation authoring because an amount is unresolved.
Raw detached flows can be calculated directly. They require declared Model Values
and resolvable references before they can participate in a saved formulation.

Share deterministic selection and coordinate preparation between these routes.
Preserve all participating references, target periods, membership, ordering,
conversion factors and fixed weights. A resampled total must be expressible as an
equation over its contributing original Movements, not only as a stored amount.
Retain intermediate relations through chained resampling and aggregation. Resolve
hierarchy membership against the pinned Model; do not make contributor selection
depend on unknown quantities within the supported finite formulation route.

Keep arithmetic acceptance independent of Polars output and compiler coefficients.
Shared coordinate rules do not justify using the calculation result as its own
numerical oracle. Zero-fill policies must not turn declared unknowns into constants;
any structural zero in a formulation must follow an explicit mapping policy.
Arbitrary Python reducers require an explicit symbolic definition and compiler
support before they can be used in an investigation.

Numerical transformations do not become formulations by tracing arbitrary Python
or Polars expressions. For a saved chain, declare the required intermediate Flow
shapes and its equations explicitly. A Stream containing numerically transformed
amounts must not be accepted as if its original Value IDs describe those amounts.
Use original Model-backed selections for formulation operands; use explicit
resampling formulations for the corresponding temporal relationships.

### Share coordinate preparation without sharing solve state

Extract deterministic alignment and grouping into a private model-owned module,
initially `model/_flow_mapping.py`. Both calculations and formulation builders use
it. It accepts declared shapes and policies and returns transient coordinate and
membership data. It must not read magnitudes, assign roles, import Polars or invoke
execution. Keep this helper focused on the existing shared callers.

The mapping identifies each group, participating Movement UUIDs, stable order,
declared coordinates and fixed calendar weights. It distinguishes an absent
coordinate from a declared Movement with an unknown amount. Unit interpretation
continues through the existing UnitSystem; any conversion factors or offsets used
by a consumer are checked explicitly. Numerical unit support does not expand the
executor's offset-unit capability.

The calculation path joins this mapping to known amounts and masks, then evaluates
the selected operation in Polars. The formulation path creates Reference and
Expression records from the same membership and fixed weights. Compilation reads
those expressions after applying Specification assignments. Acceptance evaluates
the original expressions against candidate quantities independently of compiled
rows and Polars results.

This mapping is neither a saved Model record nor a second expression language.
Do not serialize private frames, caches or a second authoritative operation graph.
Keep generic hierarchy selection with the hierarchy owner and pass its resolved
contributor IDs into the shared Flow mapping.

### Lock and unlock through Specifications

Add convenience methods for locking and unlocking that build or revise
Specification assignments and unknown references. They must not add permanent role
flags to Flow, Movement or Value. Support both an entire Flow and selected
Movements. Preserve the existing `assign_flow` and `unknown_flow` semantics.

Unlocking a quantity removes its effective assignment and declares it unknown;
locking supplies an explicit quantity, or explicitly copies a recorded amount.
The original equation and symbol identity stay unchanged. Where a role comes from
an included Specification, revise the relevant contribution or composition
explicitly. Do not silently override a conflicting included assignment.

Place `lock` and `unlock` convenience on the existing Specification facade and use
`specification/targets.py` for scalar/Flow target expansion. Each change returns a
new Specification with an explicit revision ID and predecessor; it does not save
or execute it. Require the matching Model when expanding Flow selections. Keep
copying recorded values explicit, through `assign_flow` or a clearly named
recorded-value option; an omitted quantity must not silently mean reuse.

Apply each role change atomically: a lock removes the corresponding local unknown
and estimate, and an unlock removes the corresponding local assignment. Preserve
unrelated roles, bounds, objectives and policies. Reject policy-controlled targets
and inherited conflicts. Revalidate the effective composition before execution.
Changing a role must not leave a Quantity or estimate cached as an assignment.

### State solve capability and loss of information

The current executor supports affine feasibility after assignments. Sums, fixed
weighted means, fixed FIRST/LAST selections and fixed-grid sum resampling can be
expressed within that slice. A product is supported when at least one factor is
fixed. Unknown products, divisors and nontrivial powers, unknown-dependent
MIN/MAX branches, and arbitrary function calls are not currently supported.
Supporting an expression in the schema or in Polars does not establish solver
support for each possible choice of unknowns.

Resampling does not imply a unique inverse. An annual total and twelve unknown
monthly amounts give one equation for twelve unknowns. Add independent constraints,
fixed allocation weights, or further assignments when a particular monthly result
is required. Preserve diagnostics for underdetermined and inconsistent cases;
never describe one feasible candidate as the unique reconstruction. Do not infer
allocation weights from the last recorded amounts.

General nonlinear solving remains a separate capability with its own backend and
acceptance contract. The present change must retain expressions that a future
backend could use, and must reject unsupported current investigations explicitly.

| Operation | Known-data path | Formulation and execution scope for this phase |
| --- | --- | --- |
| Aligned sum and hierarchy sum | Polars bulk reduction | Equations over all declared terms; affine |
| Fixed-grid resampling SUM | Grouping and sum | Each aggregate Movement equals the sum of its grouped aggregand Movements |
| Resampling MEAN | Explicit observation or elapsed weighting | Fixed weights and denominator from declared membership; affine |
| Resampling FIRST/LAST | Stable source order | Equality to the selected Movement; no hidden carry-forward |
| Product, growth, interest and discount | Existing numeric operations | Preserve symbolic operands; the current compiler decides support after assignments |
| MIN/MAX with unknown operands | Numeric methods remain available for known data | No new piecewise solver lowering in this phase |
| Arbitrary Python reducer | Existing callable calculation path | Requires a separately declared expression and supported compiler path |

The formulation route includes every selected declared symbol even when its amount
is null. It must not reuse numeric SKIP masks or a known-only mean denominator.
Reject such policies for passive authoring unless the caller first makes an
explicit structural selection. Empty groups require an explicit rule; zero-fill
can declare an empty sum as zero but cannot replace an unknown symbol with zero.

## Target developer interface

The common case needs line-item labels and a time grid, without a manually authored
Model or dataframe joins:

```python
from datetime import date

from rangekeeper.model.flux import Flow, Stream
from rangekeeper.model.duration import Span, Frequency
from rangekeeper.calculations.series import ResamplingMethod

operations = Span.from_duration(
    name="Operations",
    start=date(2001, 1, 1),
    frequency=Frequency.YEAR,
    count=11,
)
annual_periods = operations.periods(Frequency.YEAR)

income = Stream({
    "Potential gross income": potential_gross_income,
    "Vacancy allowance": vacancy,
})

annual_income = income.resample(
    annual_periods,
    method=ResamplingMethod.SUM,
)
annual_income.display()
effective_gross_income = annual_income.sum()
```

The input flows in this example may come from manual authoring, imported data,
projections or other calculations. The same interface applies to all of them.
If they already use matching periods, `income.sum()` needs no resampling step.

| Operation | Result and contract |
| --- | --- |
| `Stream({label: flow, ...})` | Ordered collection; labels are separate from source identity |
| `Stream.from_values(model, value_ids)` | Collection retaining the exact source revision and Value identities |
| `stream.select(...)` | Selected collection, by labels or explicit source Value IDs |
| `stream.merge(other)` | Combined collection with explicit collision and duplicate handling |
| `stream.trim(span)` | New collection restricted to the span, retaining whole-period rules |
| `stream.resample(periods, method=...)` | New Stream on the target grid |
| `stream.aggregate(method=...)` | Detailed result containing the combined Flow and coverage |
| `stream.sum()`, `.min()`, `.max()` | Convenience methods returning the combined Flow |
| `stream.display()` and notebook rich display | Readable table using one presentation implementation |
| `stream.to_frame()` | Detached numeric Polars table |

Resampling accepts one method for the collection or a complete mapping from line
labels to methods. Mean weighting can likewise be declared for the lines that use
a mean. Unknown labels and incomplete method mappings fail clearly. Do not guess
whether an amount represents receipts, a rate or a closing balance from its units.

```python
annual = financials.resample(
    annual_periods,
    method={
        "Rent receipts": ResamplingMethod.SUM,
        "Debt balance": ResamplingMethod.LAST,
    },
)
```

### Declare relationships using the same selections

The following target example assumes the Model already declares the component,
monthly-total and annual-total Flow shapes. Their amounts may all be unresolved.

```python
from uuid import uuid4

from rangekeeper.model.flux import Stream
from rangekeeper.model.formulation import flow
from rangekeeper.calculations.series import ResamplingMethod

income = Stream.from_values(model, [rent_id, vacancy_id])

monthly_relation = flow.sum(
    model,
    id=uuid4(),
    summands=income,
    total=monthly_income_id,
)
annual_relation = flow.resample(
    model,
    id=uuid4(),
    sequence=monthly_income_id,
    resampled=annual_income_id,
    method=ResamplingMethod.SUM,
)
```

The proposed sum signature exposes both mathematical roles directly:

```python
def sum(
    model: Model,
    *,
    id: UUID,
    summands: Stream | Sequence[UUID],
    total: UUID,
) -> Formulation:
    ...
```

For `flow.sum`, accept an original Model-backed Stream selection or ordered
sequence of Flow Value UUIDs as `summands`. `total` identifies the Flow Value
related to their sum. Check the exact Model revision and apply any explicit
coordinate selection. Reject detached numerical transformations as summands
with guidance to declare the intermediate Flow and relationship. There is one
expression builder for either selection input form.

Add `flow.resample(sequence=..., resampled=..., method=..., weighting=...)`.
Both Flow Value IDs are explicit; the `resampled` Flow's declared periods define the grid.
The shared mapping checks coordinate type, period bounds and membership. SUM, MEAN and
FIRST/LAST authoring use the capability table above. In the first implementation,
MIN/MAX formulation requests fail with a capability diagnostic. Keep the rich
numeric resampling API independent of that symbolic subset.

Both builders return Formulations. The caller adds them in one explicit Model
revision and pins Specifications to that revision. A forward Specification can
assign the component Movements and solve monthly/annual totals. A reverse
Specification can assign the annual total and sufficient other quantities, then
solve a selected component. Every referenced intermediate still needs an explicit
assignment, unknown role or supported policy control in that investigation.

The existing expression constructors remain the route for a custom equation.
Improve their examples with mathematical variable names; do not introduce a second
DSL, implicit Python tracing or expression-operator overloading in this change.

## Implementation sequence

Implement these stages in dependency order. Update current API documentation when
each stage lands; keep the notebooks deferred until the final codebase gate.

| Stage | Primary owner | Completion evidence |
| --- | --- | --- |
| 1. Baselines and acceptance example | Tests, examples and benchmark tooling | Current identities/results captured; expected forward/reverse quantities specified independently |
| 2. Public names | `model/flux.py`, formulation builders and `calculations/series.py` | Maintained callers migrated; existing declaration identity fixtures unchanged |
| 3. Calendar and coordinate preparation | Duration behaviours, generator and `model/_flow_mapping.py` | Span methods, exact mapping and unknown-safe grouping contracts pass |
| 4. Stream and bulk arithmetic | `model/flux.py`, `calculations/series.py` and private calculation support | One reusable frame preparation; numeric equivalence and cache isolation pass |
| 5. Formulations and roles | `model/formulation/flow.py`, `specification/specification.py`, `specification/targets.py` | Sum/resampling declarations and lock/unlock investigations pass |
| 6. Hierarchy and display | `model/system/reduction.py`, formulation hierarchy authoring, presentation adapters | Contributor parity, hierarchy reverse solve and minimal table examples pass |
| 7. Whole-codebase acceptance | Tests, schema/install checks, benchmarks and current docs | All required evidence passes; remaining external gates reported |

### Capture correctness and performance baselines

Record the source revision, local changes, interpreter, dependency versions and
hardware. Capture representative results and timings from the existing calculation
APIs before changing them. Include input preparation and result construction.
Keep independent scalar expectations for arithmetic; an earlier implementation is
not the only correctness reference.

Use small executable Python cases for the proposed Stream interface and hierarchy
workflow. These become acceptance examples without changing the notebooks.

Use the current temporal forward/inverse test and account declaration identity
fixtures as starting evidence. Write the new connected component/resampling/
hierarchy example and its independent expectations before replacing arithmetic.
It becomes fully executable as stages 3 through 6 land; do not pretend the current
API already implements the new operations.

### Rename the module and calculation choices

Move the public Flow module to `model/flux.py` and update maintained Python imports,
typing fixtures and current API references. Do not add a forwarding `model.flow`
module or restore the retired top-level `rangekeeper.flux` path.

In `calculations/series.py`, rename:

| Current name | Accepted name |
| --- | --- |
| `ResamplingReduction` | `ResamplingMethod` |
| `AggregationReducer` | `AggregationMethod` |
| `resample(..., reduction=...)` | `resample(..., method=...)` |
| `aggregate(..., reducer=...)` | `aggregate(..., method=...)` |
| `Alignment.reduce(..., reducer=...)` | `Alignment.reduce(..., method=...)` |

Keep ResamplingMethod members SUM, FIRST, LAST, MEAN, MIN and MAX. Keep
AggregationMethod members SUM, MIN and MAX. Retain MeanWeighting. These are typed
calculation choices, defined once beside their operations. The existing callable
`reducer=` on hierarchy Reduction remains a distinct extension point.

Remove retired enum names and keywords without compatibility aliases. Update live
Python callers together. Notebook import and API changes belong to the later
notebook phase; record that dependency instead of claiming walkthrough acceptance
or adding aliases to keep old notebook cells running.

Apply the complete formulation keyword inventory in this same API migration.
For the same builder UUID and participating records, compare full generated
Formulation data before and after the rename. Keep declaration names and IDs
stable. The broader module move affects adapters, calculations, scenarios, example
builders, tests and schema typing/install probes; update maintained callers even
where they do not call a formulation builder.

### Add Span methods

Add `Span.from_duration()` and `span.periods()` through the record behaviour
mechanism. Reuse `offset`, `make_periods` and `periods_between`. Add a Span-specific
behaviour mixin where needed and update the generator mapping. Do not edit generated
classes manually or introduce a separate calendar engine.

Preserve date-only inputs, start-inclusive and end-exclusive boundaries, anchored
month offsets, leap-year handling and explicit partial-period choices. A Span does
not own a frequency. Its same extent can produce monthly or annual periods.

No persistent schema fields or schema version change are required by these methods.
Keep the useful free functions as the underlying calendar operations.

### Extract coordinate preparation

Move shared shape/coordinate rules out of numerical loops and the current
formulation-only alignment implementation. Keep
`flow.aligned(members=..., reference=...)` as a small authoring helper over this
shared mechanism. The reference Flow fixes row order without assigning a solve
role. Preserve the returned coordinate matches and the existing positional policy
calls; update keyword calls to the new names.
Prepare each declared shape once per operation. For interval grouping, use the
ordered nonoverlapping grid with indexed or sweep-based membership rather than
scanning all target periods for every Movement. Preserve explicit rejection of
boundary crossings and out-of-grid entries.

The transient mapping is independent of recorded amounts, so the same membership
can feed Polars groups and equations over unresolved records. Verify it against
independent coordinate cases before optimizing its consumers. This is shared
preparation, not a second numerical backend.

### Implement Stream and the bulk calculation backend

Retain original input references, line order, labels and source metadata separately
from transformed calculation columns. Preserve useful Model-backed selection and
merge behaviour. Source access must not present a transformed Flow as the original
stored Value. Repeated source Value IDs must not silently multiply contributions;
conflicting revisions or labels require explicit resolution.

Build a typed long table with one row per movement when calculation first needs
it. Represent flow identity, movement identity, ordering, event coordinates,
period boundaries, optional recorded dates and magnitudes without opaque Python
object columns. Keep per-flow units, labels and Model/Value references in associated
metadata. Preserve evidence and field-presence information through keyed metadata
or typed columns as appropriate.

Use native Polars expressions for built-in numerical operations. Prepare the
collection and its coordinate/group mapping once, then batch joins, supported unit
normalization, reductions and known-value masks. Avoid one dataframe join or one
repeated movement-to-period scan per constituent Flow. Preserve the complete target
grid, including empty periods; grouped output alone is not sufficient.

Use compact per-collection flow/group indices in hot columns and retain the UUID
mapping in immutable metadata. Fixed conversion parameters can be joined by flow
index after UnitSystem validation. Group by flow and period for resampling; group
by coordinate across selected flows for aggregation. Stable movement order remains
an explicit column for FIRST/LAST. Coverage uses original presence/known masks,
not the post-fill magnitudes. Do not use Python row UDFs for built-in arithmetic.

Reuse prepared columns through select, trim, resample, display and repeated
aggregation. Resampling should not rebuild every intermediate Movement just to
convert those records back into columns for the next operation. Materialize Flow
records when a public result or explicit record access requires them. New results
follow the existing Movement identity rules.

Use one shared backend for standalone series functions, Stream and Flow hierarchy
reductions. Stream owns coordination, not a second set of numerical algorithms.
Use lazy expressions or cached materialized columns where measurements justify
them; keep the choice private. A LazyFrame alone does not guarantee reuse between
separate collections, so verify that repeated operations avoid repeated preparation.

Cache scope follows an immutable Stream instance and its exact input revision or
detached records. Include grid, method, weighting, units, missingness and selection
in operation reuse decisions. Never reuse numeric caches across Model revisions or
Specification role changes. Sharing immutable buffers between selections is
permitted; measure retained memory when a small selection outlives a large Stream.
An exported frame must not provide a route to mutate internal state.

Keep optional imports lazy. Constructing records or a Stream must not load Polars,
plotting libraries, notebook machinery or solvers. Use the existing calculations
extra when a numerical or table operation requires Polars.

Do not force small intrinsic Flow operations through a dataframe when conversion
cost outweighs the calculation. Use the shared backend for bulk work where it
improves the complete operation. Do not create competing fallback engines for the
same aggregation contract.

### Implement passive formulations and role editing

Extend the existing Flow builders with Stream selection support and the resampling
builder described above. Never call numeric `stream.sum()` to construct an
equation. Resolve declared shapes without requiring resolved magnitudes. Keep
membership, weights, units and ordered reference occurrences inspectable.

Keep role editing on Specification and target expansion in `targets.py`; do not
add a parallel investigation record. Validate changes through the existing local
and composition checks. Cover all periods, selected Movement UUIDs and scalar
References. Pin exact revisions when reusing a solved Model for a later inverse
investigation. Keep former solutions available as recorded quantities without
automatically assigning them.

Preserve current compiler capability checks, solver limits and independent
acceptance. New affine formulations should lower through existing arithmetic.
Do not replace the solver with a Polars reduction or rewrite a declared equation
into a different formula based on the requested output. General nonlinear support
requires a separate implementation and acceptance decision.

### Add display and table projection

Extend `adapters/polars.py` for Stream projection and add a focused presentation
adapter for HTML and plain text. Stream methods delegate to these adapters. Reuse
prepared columns and one projection contract for all display forms.

Default display preserves line order, shows units, uses readable period labels,
formats currency without machine locale, and distinguishes zero, absence and
unknown amounts. Rounding affects display only. Provide a transpose option for
proforma layouts. Escape labels in HTML and do not display schema or UUID details
unless requested.

Display does not resample, allocate amounts or invent payment dates. If temporal
representations need a common grid, give a diagnostic that identifies the conflicting
lines and the required operation. `to_frame()` must not expose a mutable handle
that can change Stream state.

### Extend hierarchy reduction to flows

Extend `model/system/reduction.py` to select and combine Flow Values while retaining
its scalar Quantity behaviour. Reuse existing hierarchy validation and source Value
selection. Add a concise Flow factory and common contributor choices:

```python
from rangekeeper.model.system import Reduction, Contributor
from rangekeeper.calculations.series import (
    AggregationMethod,
    ResamplingMethod,
)

cashflow_rollup = Reduction.flows(
    key="net_cashflow",
    periods=annual_periods,
    resampling=ResamplingMethod.SUM,
    aggregation=AggregationMethod.SUM,
    contributors=Contributor.LEAVES,
)

result = cashflow_rollup.execute(hierarchy)
building_cashflow = result.value(building_id)
portfolio_cashflow = result.root_value
result.display()
```

Contributor supplies LEAVES and ALL; retain predicate-based selection. Keep source
Value IDs, owner coverage and period-level availability inspectable. Do not collapse
these different coverage measures into one fraction.

Prepare selected flows and hierarchy structure once. Batch built-in reductions
through the shared backend. Avoid repeated conversion and rescanning of the same
descendants for each parent. Check the memory cost of hierarchy expansion as well
as arithmetic time. Custom reducers retain their callable path and error behaviour;
they need not have native Polars performance.

Combine original contributors where reducer semantics require it. Do not compute
means from unweighted subtree means. Keep membership and relationship hierarchies
explicit, reject ambiguous topology, and prevent unintended addition of parent
totals to their constituents. Scalar behaviour must remain covered by regression
tests throughout this extension.

Results do not revise or persist a Model, create governing equations, manufacture
evidence Claims, run a solver or publish a Run.

This boundary applies to numerical results. The explicit formulation-authoring
route above returns passive equations over the same selected contributors and
coordinate mapping; it does not execute or publish them.

Add an explicit `Reduction.formulate(hierarchy, id=..., aggregates=...)` route for the
built-in SUM rule. `aggregates` maps requested entity UUIDs to already declared Flow
Value UUIDs in the same Model revision. Delegate equation construction to
`model/formulation/hierarchy.py`; contributor selection remains with Reduction.
Return a canonical Formulation containing the required equations and bindings.

Split structural selection from the existing amount-reading `_contribution` path
so unresolved but declared Flow Values remain valid symbolic contributors. Use
the same entity and Movement membership as numeric `execute`. Default equations
sum the selected original contributors for each requested total. If declared child
totals are used to express a multilevel chain, their contribution sets must be
disjoint and complete for that parent equation. A stored parent total must not be
silently added to its own descendants.

For mixed grids, express the rule's fixed resampling groups as sums or weighted
terms over the original Movements. If a resampled intermediate must itself be
locked, solved or inspected as a Model quantity, declare its Flow and resampling
relationship explicitly. Preserve these intermediate references in a declared
chain. Reject selection that depends on unknown amounts, arbitrary callable reducers
and unsupported symbolic methods
in `formulate`, while keeping their applicable numerical paths. The same hierarchy
can support either a report or an acausal investigation without hiding which was
requested.

## Preserved calculation contracts

- Exact coordinate alignment is the default. Union or intersection is explicit.
  Labels and UUIDs do not replace the established movement matching coordinates.
- Stream and Reduction retain declared policies so callers need not repeat them
  for every method. Operation-level overrides remain explicit.
- MissingValueHandling.ERROR remains the default for numerical work. Zero-filling,
  skipping or propagation requires an explicit policy; display can show unknown
  values without resolving them.
- A missing coordinate, an unresolved movement and a known zero remain distinct.
  Zero-filling applies only where the selected policy permits it. Polars null and
  empty-group defaults must not silently define Rangekeeper's missing-value rules.
- Resampling combines movements within a target period. Aggregation combines flows
  at matching coordinates. Flow.total sums movements over time.
- FIRST and LAST require stable source order. They do not carry values into gaps.
  MEAN requires observation or elapsed-time weighting, with bounded periods for
  elapsed weighting.
- Movements outside or crossing target boundaries retain explicit handling.
  Trimming, allocation and interpretation as dated payments are separate decisions.
  Annual-to-monthly allocation is not inferred by resampling.
- Units are checked before arithmetic. Compatible units are converted; incompatible
  units cannot be added. Time dimensions are not removed implicitly.
- Source records, field presence, Claims and exact revision references remain
  intact. Derived Movement IDs follow the current identity contract.
- Preserve numerical acceptance, including cancellation-sensitive sums. Compare
  native reductions with independent expectations and existing tolerances. Do not
  weaken tolerances to obtain a speed result; retain a suitable stable summation
  strategy where needed.
- Keep resampling diagnostics distinct from later aggregation diagnostics.
  Extracting a plain Flow does not preserve an entire operation history. Detailed
  results remain the route for contribution and coverage inspection.

## Verification and performance acceptance

Run focused checks during implementation, then the complete local suite, typing,
applicable generator checks, installed-wheel checks and documentation checks. Use
the root commands and environments in [verification](../contributing/verification.md)
and [schema development](../contributing/schema.md).

| Area | Required evidence |
| --- | --- |
| Calendar | Leap years, month ends, span bounds, anchored frequencies and partial periods |
| Collection | Direct and Model-backed inputs, order, labels, selection, merging, duplicate detection and source pins |
| Resampling | Each method, mean weighting, mixed frequencies, sparse periods and rejected boundary crossings |
| Arithmetic | Independent totals, compatible unit conversion, incompatible units, overflow and cancellation |
| Missingness | Zero, absent coordinates, unknown amounts, all-missing groups and coverage after zero-filling |
| Identity | Input immutability, retained and fresh IDs, Claims, source revisions and record round trips |
| Naming | Complete maintained caller migration; byte-equivalent declaration data for the same authoring inputs; unchanged frozen identity fixtures |
| Hierarchy | Multiple levels, contributors, parent totals, custom reducers, scalar regressions and per-period gaps |
| Acausal behaviour | Same equations solved with different roles; scalar and partial-Flow assignments; sum, fixed-weight resampling and hierarchy formulation parity; underdetermined, inconsistent and unsupported investigations |
| Presentation | Matching HTML/text content, readable units and labels, escaping, transpose and unchanged numeric values |
| Packaging | Minimal imports, optional dependency diagnostics and examples executed from an isolated wheel |

Benchmark representative workloads, using identical inputs and contracts for the
baseline and candidate. Include the following starting sizes; record any adjustment
and its reason before comparing results:

| Workload | Starting shape | Operations |
| --- | --- | --- |
| Walkthrough | 3 flows over 11 annual periods | Construct, display and sum |
| Repeated reporting | 100 flows over 120 monthly periods | Select, annual resample, repeated reductions and display |
| Large collection | 1,000 flows over 360 monthly periods | Alignment, annual resample and aggregation |
| Hierarchy | 100 buildings with 10 contributors each over 120 periods | Prepare, aggregate at each level and inspect selected totals |
| Sparse inputs | Unequal spans and frequencies at reporting and large-collection sizes | Explicit grid preparation, missing rules and coverage |

Where the current high-level API does not exist, construct the baseline from the
existing Flow and series operations over the same selected contributors. Compare
equivalent Flow results; scalar hierarchy timing is not a Flow hierarchy baseline.

Measure cold preparation separately from repeated operations on an existing Stream.
Record elapsed-time distributions and peak memory, including conversion, validation,
unit handling, identity generation and output-record construction. Fix thread
settings and dependencies for comparable runs. Verify numerical results outside
timed regions. Use stable repeated samples rather than a single fastest run.

Performance acceptance requires measured improvement beyond run-to-run variation
for the targeted medium and large bulk operations and repeated reporting. Report
small-case overhead in absolute time, identify material regressions and resolve
them. Do not claim an arbitrary speed multiplier or infer gains from an isolated
Polars group-by benchmark. If record construction dominates after the bulk changes,
record that evidence for a separate Flow storage decision.

Define an acausal acceptance example before changing the bulk backend. Declare a
monthly component sum, annual resampling and a parent hierarchy total. Solve
forward, then fix a different total and solve a selected component or month with
the same equations. Check against independent expected quantities. Include a case
with enough fixed monthly values for a unique answer and a separate case with
insufficient information. Verify that all-unknown inputs, recorded prior results,
display calls and warmed Polars caches do not change equation references or roles.
Use the existing temporal forward/inverse execution tests as a regression baseline,
not as proof that the new collection-to-formulation route is already implemented.

Use this concrete acceptance case, with all amounts in one compatible currency:

1. Declare monthly rent and signed expenses for two buildings, monthly net flows,
   annual net flows and an annual portfolio total. Use fixed calendar coordinates.
2. Building A has rent 100 and expenses -20 in each of twelve months; its annual
   net is 960. Building B has rent 200 and expenses -50; its annual net is 1,800.
   Forward solving must produce a portfolio total of 2,760.
3. Keep those equations. Fix the portfolio total to 2,880, all expenses, all of
   building B's rent and eleven months of building A's rent. Solve the remaining
   rent and intermediate totals. The remaining rent must be 220 and A's annual
   net must be 1,080. Run this from an accepted output revision too, to prove that
   prior amounts are not permanent assignments.
4. Unlock two months in A instead. Their required sum is 320; no individual split
   is uniquely determined by these equations. Check the diagnostic without
   requiring one solver-specific split.
5. Fix every original component and impose the changed portfolio total. Require
   an infeasible conclusion and no published output.

Add separate fixed-weight MEAN and FIRST/LAST cases, heterogeneous unit conversion,
absent coordinates, null amounts, duplicate contributors and stale Model pins.
Test an unsupported nonlinear role selection as a failure with no output. Retain
independent tampered-candidate rejection tests. A fully unresolved set of Flow
shapes must permit formulation construction before solve roles exist.

Keep the numerical benchmarks separate from solver scalability claims. The current
default limits are 10,000 symbols and 20,000 affine constraints per leaf, and
expression expansion has its own cost. A 1,000-by-360 numeric Stream benchmark
does not prove the same-sized acausal problem is supported. Measure preparation,
equation construction and solving separately for bounded representative models.
Honor the existing limits and preserve useful diagnostics instead of increasing
them to make an example pass.

## Dependencies and exclusions

Baseline capture precedes backend changes. The module and enum migration precedes
new caller code. Calendar methods and the shared columnar preparation feed Stream;
Stream and the backend feed presentation and Flow hierarchy reduction. Define
the acausal acceptance example and its independent expectations before bulk
arithmetic changes, and verify the shared mapping contract first. Complete the
connected executable example as formulation and hierarchy integration land.
Codebase acceptance, including reverse-solving checks, precedes notebook migration.

This phase excludes notebook narrative and output migration, canonical Flow storage
replacement, new persistent schema fields, automatic allocation or interpolation,
new general graph semantics, solver changes, a configurable backend plugin system,
held legacy deletion, native host acceptance and site publication. It does not add
a pandas path or a new dependency merely to format tables.

Here, excluded solver changes means new nonlinear, piecewise, objective or backend
capabilities. Integration tests, capability diagnostics and execution regression
checks are required. No schema migration, new expression language, automatic
causalization of arbitrary Python or global mutable cache is part of this plan.

The public module rename will require later notebook import changes. Until those
notebooks are migrated and executed, the codebase result is not walkthrough or
release acceptance for the complete example set.

## Deletion targets and code growth

Remove the old public `model/flow.py` module, retired enum names and changed keyword
paths. Replace the existing selection-only Stream implementation rather than keep
a second Stream type. Remove duplicated per-flow preparation, coordinate encoding,
period scans and record/frame round trips where the shared bulk implementation
supersedes them. Preserve independent tests and acceptance oracles.

Remove the retired formulation keywords and duplicated alignment implementation.
Remove the dedicated `financial.reversion` helper after its retained pattern and
direct test caller are migrated; keep generic expression and mapping facilities.
Retain the public `aligned` helper where the example policy and builders use it,
with named `members` and `reference` parameters and one mapping implementation underneath.
Keep historical declarations and fixtures unchanged. Move generic contributor selection
out of amount-specific collection only as far as both numeric and symbolic callers
need it. Do not duplicate the hierarchy traversal in a new formulation framework.

The later notebook phase removes its unnecessary Model-authoring helper and manual
display joins where the new Stream handles the same teaching step. Those deletions
do not count as delivered code reduction in this phase.

Report before/after lines separately for handwritten runtime, generated code,
tests/examples and documentation. Net runtime growth is justified for collection
coordination, reusable presentation, Flow hierarchy aggregation, passive resampling
and hierarchy equations, and explicit Specification role editing. File moves
alone are not reduction. Any additional helper or cache must have a clear owner,
demonstrated reuse and measured benefit or a required contract.

## Documentation and completion

During implementation, update the authoritative architecture, calculation, table,
system, record, identity and upgrade references with the behaviour that actually
lands. Keep this decision indexed with its real status. Preserve historical source
snapshots and benchmark evidence; do not rewrite old results to match the new API.

Codebase completion requires:

1. The short Stream example and a multilevel Flow hierarchy example work from the
   same installed candidate wheel.
2. The stated correctness, identity, coverage and import contracts pass their checks.
   The explicit collection-to-formulation route also passes forward and reverse
   investigations without freezing recorded amounts or losing source references.
3. Comparative performance results cover complete operations and satisfy the
   performance acceptance above.
4. The old public module and enum names are absent from maintained Python callers;
   deferred notebook migration and historical references are identified separately.
   Directional formulation keywords are replaced according to the naming inventory,
   with existing equation content and stable identity fixtures preserved.
5. Current documentation matches the implementation and local documentation checks
   pass. All remaining work and untested platforms are recorded explicitly.

The notebook-facing follow-up on 2026-10-08 adds `Flow.display(name=...)` and
rich notebook display through the shared Stream renderer. The agreed projection
verbs are `extrapolate(initial=..., periods=...)` and
`distribute(quantity=..., periods=..., distribution=...)`, replacing `project`
and `allocate` without aliases. `Distribution`, `negate()` and `collapse()` retain
their meanings. See the [API acceptance](../research/basic-dcf-2026-10-08/api.md).

The first walkthrough is migrated from its legacy teaching baseline, with its
guidance, intermediate inspections and financial example retained. Its 26 code
cells execute in a fresh kernel against the candidate wheel and reproduce the
$1,000 present value. See [notebook acceptance](../research/basic-dcf-2026-10-08/README.md)
for the teaching mapping, rendered review and build scope. Apply this approach to
the remaining six notebooks next; their migration and full-book acceptance remain
open.

## Source and caller checklist

Use this checklist at implementation start; refresh it if the checkout changes.

| Concern | Current owner or caller to migrate/check |
| --- | --- |
| Public Flow module | `src/rangekeeper/model/flow.py` to `model/flux.py`; imports in calculations, adapters, scenarios, examples and tests |
| Equation parameter names | `src/rangekeeper/model/formulation/{flow,growth,financial,account}.py`; `model/expression/authoring.py` for separate operator parameters |
| Stable declarations | `model/formulation/authoring.py`; `src/tests/fixtures/formulation_identity.json` and `legacy_declarations.json` |
| Direct builder tests | `src/tests/test_temporal_execution.py`, `src/tests/test_account_schedule.py` |
| Positional alignment caller | `examples/rangekeeper_examples/investment.py` resale policy builder |
| Numeric series | `src/rangekeeper/calculations/series.py`; `src/tests/test_calculations.py`, `test_flow_operations.py`, `test_reference_identity.py` |
| Span behaviour | `schema/behaviors`, `model/duration`, behaviour mapping in `tools/schema/generate.py`; `test_duration_calendar.py` |
| Hierarchy and selection | `src/rangekeeper/model/system/reduction.py`; `src/tests/test_model_graph.py` and Flow operation checks |
| Specification roles | `specification/specification.py`, `targets.py`, `composition.py`, `validation.py`; domain/temporal/role conflict checks |
| Solver boundary | `run/execution/{preparation,compiler,acceptance,publication,implementation}.py`; execution and temporal regression tests |
| Presentation | `src/rangekeeper/adapters/polars.py`; retain its existing lossless Flow interchange separately from Stream display projection |
| Typing and installation | `tools/schema/typing_behavior_{valid,invalid}.py`, `verify_install.py`, `cross_language.py`; optional import checks |
| Current documentation | Architecture; records, calculations, expressions, Specifications, execution, system and table references; scenarios/policies and upgrade guidance |
| Teaching migration | `examples/walkthrough/basic_dcf.ipynb` accepted; remaining six notebooks and full-book acceptance deferred |

Review implementation fingerprint manifests when moving or adding code that their
consumers execute. Add actual semantic dependencies where needed, without including
unrelated authoring/presentation modules merely because their names changed. A
declaration interface change alone must not require rewriting stored Models or Runs.

## Related contracts

- [Architecture](../concepts/architecture.md) and
  [ADR-004 package ownership](004-package-and-project-ownership.md).
- [ADR-003 computation and evidence](003-computation-and-evidence.md).
- [Expressions](../reference/expressions.md),
  [Specifications](../reference/specification.md) and
  [execution capability](../reference/execution.md).
- [Calculations](../reference/calculations.md), [records](../reference/records.md)
  and [identity](../reference/identity.md).
- [System reductions](../reference/system.md) and [tables](../reference/tables.md).
- [Walkthrough acceptance](../guides/walkthroughs.md) and
  [documentation lifecycle](../contributing/documentation.md).

This accepted design extends the existing calculation and ownership decisions.
The acceptance record above identifies the delivered implementation and its limits.
